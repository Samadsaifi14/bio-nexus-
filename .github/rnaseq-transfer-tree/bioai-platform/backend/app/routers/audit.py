from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from app.deps import limiter
from app.services.supabase import get_supabase
from app.services.audit_engine import run_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])
_SESSION_EVENT_COUNTS: dict[str, int] = {}
_AUDIT_INTERVAL = 5
_MAX_SESSIONS = 1000
_MAX_SUMMARY = 240


class AuditEventIn(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    step: str
    tool: str
    status: str
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: int = 0
    metadata: Optional[dict] = None
    timestamp: Optional[str] = None


def _compact(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)\b[ACDEFGHIKLMNPQRSTVWYBXZJUO]{24,}\b", "[sequence-redacted]", text)
    text = re.sub(r"https?://\S+", "[url-redacted]", text)
    text = text.replace("Traceback (most recent call last):", "")
    return text[:_MAX_SUMMARY]


def _sanitize_metadata(metadata: Optional[dict]) -> Optional[dict]:
    if not metadata:
        return None
    allowed = {"database", "program", "sequence_length", "hit_count", "provider", "status_code"}
    clean = {k: v for k, v in metadata.items() if k in allowed and isinstance(v, (str, int, float, bool, type(None)))}
    return clean or None


def _should_trigger_audit(session_id: str) -> bool:
    count = _SESSION_EVENT_COUNTS.get(session_id, 0) + 1
    _SESSION_EVENT_COUNTS[session_id] = count
    if len(_SESSION_EVENT_COUNTS) > _MAX_SESSIONS:
        oldest = list(_SESSION_EVENT_COUNTS.keys())[:_MAX_SESSIONS // 2]
        for k in oldest:
            _SESSION_EVENT_COUNTS.pop(k, None)
    return count % _AUDIT_INTERVAL == 0


@router.post("/event")
@limiter.exempt
async def receive_event(event: AuditEventIn, request: Request, background: BackgroundTasks):
    sb = get_supabase()
    payload = event.model_dump(exclude_none=True)
    payload["input_summary"] = _compact(event.input_summary)
    payload["output_summary"] = _compact(event.output_summary)
    payload["metadata"] = _sanitize_metadata(event.metadata)
    try:
        sb.table("audit_events").insert(payload).execute()
    except Exception as exc:
        logger.warning("Failed to store audit event (%s)", type(exc).__name__)
    should_audit = event.status == "failed" or _should_trigger_audit(event.session_id)
    if should_audit:
        background.add_task(run_audit, event.session_id, event.step)
    return {"ok": True}


@router.get("/insights")
@limiter.exempt
async def get_insights(session: str):
    if not session:
        raise HTTPException(400, detail="session query parameter is required")
    sb = get_supabase()
    resp = sb.table("audit_insights").select("*").eq("session_id", session).order("created_at", desc=True).limit(1).execute()
    return {"latest": resp.data[0] if resp.data else None}
