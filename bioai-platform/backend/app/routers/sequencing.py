from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel

from app.deps import limiter
from app.services.supabase import get_supabase
from app.services.auth import require_user_id
from app.services.ssrf import validate_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sequencing", tags=["sequencing"])

_TABLE = "sequencing_jobs"
_MAX_JOBS = 200
_JOB_TTL = 7200


def _prune_jobs() -> None:
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=_JOB_TTL)).strftime('%Y-%m-%dT%H:%M:%S')
    sb.table(_TABLE).delete().lt("done_at", cutoff).execute()
    count = sb.table(_TABLE).select("id", count="exact").execute().count or 0
    if count > _MAX_JOBS:
        to_delete = (
            sb.table(_TABLE)
            .select("id")
            .in_("status", ("complete", "failed"))
            .order("created_at", desc=True)
            .range(_MAX_JOBS, _MAX_JOBS + 500)
            .execute()
            .data
        )
        ids = [r["id"] for r in to_delete]
        if ids:
            sb.table(_TABLE).delete().in_("id", ids).execute()


class SequencingRequest(BaseModel):
    fastq_url: str
    reference: str = "sars-cov-2"


class SequencingJob(BaseModel):
    job_id: str
    fastq_url: str
    reference: str
    status: str = "queued"
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""
    done_at: Optional[str] = None


def _init(job_id: str, req: SequencingRequest, user_id: str) -> None:
    try:
        _prune_jobs()
    except Exception:
        pass
    get_supabase().table(_TABLE).insert({
        "id":        job_id,
        "fastq_url": req.fastq_url,
        "reference": req.reference,
        "status":    "queued",
        "user_id":   user_id,
        "result":    None,
        "error":     None,
        "done_at":   None,
    }).execute()


def _patch(job_id: str, **kw) -> None:
    get_supabase().table(_TABLE).update(kw).eq("id", job_id).execute()


def _read(job_id: str, user_id: str | None = None) -> dict | None:
    query = get_supabase().table(_TABLE).select("*").eq("id", job_id)
    if user_id:
        query = query.eq("user_id", user_id)
    rows = query.execute().data
    return dict(rows[0]) if rows else None


async def _worker(job_id: str) -> None:
    job = _read(job_id)
    if not job:
        return
    _patch(job_id, status="downloading")

    from app.tools.sequencing import SequencingPipeline, PIPELINE_TIMEOUT

    tool = SequencingPipeline()
    try:
        result = await asyncio.wait_for(
            tool.run({
                "fastq_url": job["fastq_url"],
                "reference": job["reference"],
            }),
            timeout=PIPELINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        _patch(job_id, status="failed", error="Pipeline timed out", done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
        return

    if "error" in result and not result.get("steps_completed"):
        _patch(job_id, status="failed", error=result["error"], done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
    else:
        _patch(job_id, status="complete", result=result, done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))


VALID_DEMO = {"synthetic", "demo", "test"}


@router.post("/run")
async def run_sequencing(req: SequencingRequest, background_tasks: BackgroundTasks, user_id: str = Depends(require_user_id)):
    if not req.fastq_url.strip():
        raise HTTPException(400, detail="fastq_url is required")
    if req.fastq_url.lower() not in VALID_DEMO:
        if not req.fastq_url.startswith(("http://", "https://")):
            raise HTTPException(400, detail="fastq_url must be a valid URL or 'synthetic' for demo data")
        validate_url(req.fastq_url)

    job_id = str(uuid.uuid4())
    _init(job_id, req, user_id)
    background_tasks.add_task(_worker, job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}")
@limiter.exempt
async def get_status(job_id: str, user_id: str = Depends(require_user_id)):
    job = _read(job_id, user_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    return job


@router.get("/references")
async def list_references():
    from app.tools.sequencing import REFERENCE_URLS
    return {
        "references": [
            {"id": k, "name": k.replace("-", " ").title()}
            for k in REFERENCE_URLS
        ]
    }
