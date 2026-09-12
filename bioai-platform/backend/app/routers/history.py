"""Owner-scoped job history DAG and branching."""
from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import require_user_id
from app.services.job_access import fetch_owned_job, fetch_owned_job_context
from app.services.supabase import get_supabase

router = APIRouter()

_HISTORY_FIELDS = "id, tool, query_preview, status, parent_job_id, created_at, completed_at, error"


class JobNode(BaseModel):
    id: str
    tool: str
    query_preview: str | None = None
    status: str
    parent_job_id: str | None = None
    created_at: str
    completed_at: str | None = None
    error: str | None = None


@router.get("/graph/{job_id}")
async def get_job_graph(job_id: str, user_id: str = Depends(require_user_id)):
    """Return owned ancestry plus direct descendants without cross-tenant reads."""
    job = fetch_owned_job(job_id, user_id, _HISTORY_FIELDS)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    supabase = get_supabase()
    ancestors: list[dict] = []
    current = job
    seen = {job_id}
    while current.get("parent_job_id"):
        pid = current["parent_job_id"]
        if pid in seen:
            break
        seen.add(pid)
        parent = fetch_owned_job(pid, user_id, _HISTORY_FIELDS)
        if not parent:
            break
        ancestors.append(parent)
        current = parent
    ancestors.reverse()

    desc_res = (
        supabase.table("jobs")
        .select(_HISTORY_FIELDS)
        .eq("parent_job_id", job_id)
        .eq("user_id", user_id)
        .execute()
    )
    descendants = desc_res.data or []

    nodes = ancestors + [job] + descendants
    edges = [
        {"from": node["parent_job_id"], "to": node["id"]}
        for node in nodes
        if node.get("parent_job_id")
    ]
    return {"nodes": [JobNode(**node) for node in nodes], "edges": edges, "focus": job_id}


@router.get("/children/{job_id}")
async def get_job_children(job_id: str, user_id: str = Depends(require_user_id)):
    """Return direct children only after confirming ownership of the parent."""
    if not fetch_owned_job(job_id, user_id, "id"):
        raise HTTPException(status_code=404, detail="Job not found")
    result = (
        get_supabase().table("jobs")
        .select("id, tool, query_preview, status, created_at, completed_at")
        .eq("parent_job_id", job_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"children": result.data or []}


class BranchRequest(BaseModel):
    source_job_id: str
    steps: list[str]
    parameters: dict | None = None


@router.post("/branch")
async def branch_from_job(req: BranchRequest, user_id: str = Depends(require_user_id)):
    """Create a new private pipeline job from an owned experiment context."""
    from app.routers.pipeline_v2 import _execute, _jobs, _jobs_lock, _persist_v2_job

    context = fetch_owned_job_context(req.source_job_id, user_id)
    if not context:
        raise HTTPException(status_code=404, detail="Source job not found")

    sequence = (context.get("query") or {}).get("sequence") or context.get("sequence") or ""
    if not sequence:
        raise HTTPException(status_code=422, detail="Source experiment has no reusable sequence input")

    new_job_id = str(uuid.uuid4())
    payload = {
        "id": new_job_id,
        "user_id": user_id,
        "tool": "pipeline_v2",
        "pipeline_type": "protein_analysis",
        "query_preview": f"sequence_length:{len(sequence)}",
        "status": "queued",
        "context_json": {"sequence": sequence, "length": len(sequence), "parent_context": context},
        "steps_completed": [],
        "progress_pct": 0,
        "parent_job_id": req.source_job_id,
    }
    _persist_v2_job(new_job_id, payload)

    with _jobs_lock:
        _jobs[new_job_id] = {
            "status": "queued",
            "steps": {step: {"status": "pending", "progress": 0, "data": None, "error": None} for step in req.steps},
            "context": {"sequence": sequence, "parent_context": context},
            "current_step": None,
            "progress": 0,
        }

    thread = threading.Thread(
        target=_execute,
        args=(new_job_id, req.steps, False, "", 100, "", "global"),
        daemon=True,
    )
    thread.start()
    return {"job_id": new_job_id, "parent_job_id": req.source_job_id}
