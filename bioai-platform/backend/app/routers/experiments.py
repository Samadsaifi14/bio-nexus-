from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.services.auth import get_user_id
from app.services.experiment import finalize_experiment, get_experiment, begin_experiment, build_fingerprint
from app.services.provenance import trace_for_job, record_step

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("")
async def list_experiments(limit: int = 20, user_id: str | None = Depends(get_user_id)):
    """Recent experiments (provenance metadata for reproducibility)."""
    from app.services.supabase import get_supabase

    try:
        sb = get_supabase()
        q = sb.table("experiments") \
            .select("experiment_id,job_id,pipeline,input_hash,git_commit,software_versions,"
                    "container_hash,database_versions,environment,random_seed,parameters,status,"
                    "started_at,finished_at,created_at") \
            .order("created_at", desc=True) \
            .limit(limit)
        result = q.execute()
        return {"experiments": result.data or []}
    except Exception as e:
        # Pre-migration the table may not exist — degrade to an empty list so
        # the UI never hard-fails (same philosophy as the best-effort services).
        if "experiments" in str(e):
            logger.warning("Experiments list degraded (table missing or unreachable): %s", e)
            return {"experiments": []}
        raise HTTPException(status_code=500, detail=f"Experiments list error: {type(e).__name__}: {e}")


@router.get("/{job_id}")
async def get_experiment_by_job(job_id: str, user_id: str | None = Depends(get_user_id)):
    """The immutable experiment record for a job, including its provenance DAG."""
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return {"experiment": exp}


@router.get("/{job_id}/provenance")
async def get_provenance(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Clickable provenance trace: nodes + edges for a job's experiment."""
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return trace_for_job(job_id, exp["experiment_id"])


@router.post("/{job_id}/finalize")
async def finalize(job_id: str, status: str, error: str | None = None):
    """Manually finalize an experiment (used by tests / admin).
    Immutable fingerprint fields are never overwritten."""
    finalize_experiment(job_id, status, error)
    return {"ok": True}


@router.post("/debug/new")
async def debug_new(job_id: str, sequence: str, pipeline: str = "debug"):
    """Create an experiment record on demand (used by tests)."""
    exp_id = begin_experiment(job_id, sequence, pipeline)
    if not exp_id:
        raise HTTPException(status_code=500, detail="Experiment creation failed")
    return {"experiment_id": exp_id}


@router.post("/debug/trace")
async def debug_trace(job_id: str, node_id: str, tool: str, deps: list[str] | None = None):
    """Record a provenance node on demand (used by tests)."""
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    record_step(exp["id"], node_id, tool=tool, deps=deps or [])
    return {"ok": True}


@router.get("/debug/fingerprint")
async def debug_fingerprint(sequence: str):
    """Return the reproducibility fingerprint for an input (used by tests)."""
    return build_fingerprint(sequence)