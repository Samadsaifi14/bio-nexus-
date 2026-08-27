"""Job history DAG — lets users trace provenance across branched runs."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.auth import get_user_id
from app.services.supabase import get_supabase

router = APIRouter()


class JobNode(BaseModel):
    id: str
    tool: str
    query_preview: str
    status: str
    parent_job_id: str | None = None
    created_at: str
    completed_at: str | None = None
    error: str | None = None


@router.get("/graph/{job_id}")
async def get_job_graph(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Return the full ancestry + descendants of a job as a DAG."""
    supabase = get_supabase()

    # Fetch the root job
    result = supabase.table("jobs").select(
        "id, tool, query_preview, status, parent_job_id, created_at, completed_at, error"
    ).eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    job = result.data[0]
    if user_id and job.get("user_id") and job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Walk ancestors
    ancestors: list[dict] = []
    current = job
    seen = {job_id}
    while current.get("parent_job_id"):
        pid = current["parent_job_id"]
        if pid in seen:
            break  # safety against cycles
        seen.add(pid)
        parent_res = supabase.table("jobs").select(
            "id, tool, query_preview, status, parent_job_id, created_at, completed_at, error"
        ).eq("id", pid).execute()
        if not parent_res.data:
            break
        parent = parent_res.data[0]
        ancestors.append(parent)
        current = parent
    ancestors.reverse()

    # Find descendants (jobs whose parent_job_id == job_id)
    desc_res = supabase.table("jobs").select(
        "id, tool, query_preview, status, parent_job_id, created_at, completed_at, error"
    ).eq("parent_job_id", job_id).execute()
    descendants = desc_res.data or []

    # Build nodes list
    nodes = ancestors + [job] + descendants
    edges = []
    for n in nodes:
        if n.get("parent_job_id"):
            edges.append({"from": n["parent_job_id"], "to": n["id"]})

    return {
        "nodes": [JobNode(**n) for n in nodes],
        "edges": edges,
        "focus": job_id,
    }


@router.get("/children/{job_id}")
async def get_job_children(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Return direct children of a job (for the 'branch from here' list)."""
    supabase = get_supabase()
    result = supabase.table("jobs").select(
        "id, tool, query_preview, status, created_at, completed_at"
    ).eq("parent_job_id", job_id).order("created_at", desc=True).execute()
    return {"children": result.data or []}


class BranchRequest(BaseModel):
    source_job_id: str
    steps: list[str]
    parameters: dict | None = None


@router.post("/branch")
async def branch_from_job(
    req: BranchRequest,
    user_id: str | None = Depends(get_user_id),
):
    """Create a new pipeline job branched from an existing job's results.

    The source job's context_json is passed as input to the new pipeline.
    """
    from app.routers.pipeline_v2 import _persist_v2_job, _jobs, _jobs_lock
    import uuid

    supabase = get_supabase()
    src = supabase.table("jobs").select("*").eq("id", req.source_job_id).execute()
    if not src.data:
        raise HTTPException(status_code=404, detail="Source job not found")
    source = src.data[0]
    if user_id and source.get("user_id") and source["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build payload from source results
    context = source.get("context_json") or {}
    sequence = (context.get("query") or {}).get("sequence") or context.get("sequence") or ""

    new_job_id = str(uuid.uuid4())
    payload = {
        "id": new_job_id,
        "user_id": user_id,
        "tool": "pipeline_v2",
        "pipeline_type": "protein_analysis",
        "query_preview": (sequence[:60] + "...") if len(sequence) > 60 else sequence,
        "status": "queued",
        "context_json": {"sequence": sequence, "parent_context": context},
        "steps_completed": [],
        "progress_pct": 0,
        "parent_job_id": req.source_job_id,
    }
    _persist_v2_job(new_job_id, payload)

    # Initialize in-memory state
    with _jobs_lock:
        _jobs[new_job_id] = {
            "status": "queued",
            "steps": {s: {"status": "pending", "progress": 0, "data": None, "error": None} for s in req.steps},
            "context": {"sequence": sequence, "parent_context": context},
            "current_step": None,
            "progress": 0,
        }

    # Spawn pipeline thread
    import threading
    from app.routers.pipeline_v2 import _execute

    thread = threading.Thread(
        target=_execute,
        args=(new_job_id, req.steps, False, "", 100, "", "global"),
        daemon=True,
    )
    thread.start()

    return {"job_id": new_job_id, "parent_job_id": req.source_job_id}
