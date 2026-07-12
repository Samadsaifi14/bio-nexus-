from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.deps import limiter
from app.services.supabase import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docking", tags=["docking"])

_TABLE = "docking_jobs"
_MAX_JOBS = 200
_JOB_TTL = 7200


def _prune_jobs() -> None:
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=_JOB_TTL)).isoformat()
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


class DockingRequest(BaseModel):
    pdb_id: str = ""
    smiles: str
    pdb_url: str = ""


class DockingJob(BaseModel):
    job_id: str
    pdb_id: str = ""
    pdb_url: str = ""
    smiles: str
    status: str = "queued"
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""
    done_at: Optional[str] = None


def _init(job_id: str, req: DockingRequest) -> None:
    try:
        _prune_jobs()
    except Exception:
        pass
    get_supabase().table(_TABLE).insert({
        "id":      job_id,
        "pdb_id":  req.pdb_id,
        "pdb_url": req.pdb_url,
        "smiles":  req.smiles,
        "status":  "queued",
        "result":  None,
        "error":   None,
        "done_at": None,
    }).execute()


def _patch(job_id: str, **kw) -> None:
    get_supabase().table(_TABLE).update(kw).eq("id", job_id).execute()


def _read(job_id: str) -> dict | None:
    rows = get_supabase().table(_TABLE).select("*").eq("id", job_id).execute().data
    return dict(rows[0]) if rows else None


async def _worker(job_id: str) -> None:
    """Run docking job — async on the main event loop (subprocess calls are non-blocking)."""
    job = _read(job_id)
    if not job:
        return

    _patch(job_id, status="importing_tool")
    from app.tools.docking import DockingTool

    _patch(job_id, status="building_params")
    tool = DockingTool()
    params: dict = {"smiles": job["smiles"]}
    if job.get("pdb_url"):
        params["pdb_url"] = job["pdb_url"]
    if job.get("pdb_id"):
        params["pdb_id"] = job["pdb_id"]

    progress_callback = lambda s: _patch(job_id, status=s)

    _patch(job_id, status="starting_docking")
    try:
        result = await tool.run(params, progress_callback=progress_callback)
    except Exception as exc:
        logger.exception("Worker crashed for job %s", job_id)
        _patch(job_id, status="failed", error=str(exc), done_at=datetime.now(timezone.utc).isoformat())
        return

    if "error" in result and not result.get("poses"):
        _patch(job_id, status="failed", error=result["error"], done_at=datetime.now(timezone.utc).isoformat())
    else:
        _patch(job_id, status="complete", result=result, done_at=datetime.now(timezone.utc).isoformat())


@router.get("/debug")
async def debug_deps():
    import os, sys, shutil
    steps = {}
    steps["python"] = sys.version
    steps["vina_in_path"] = shutil.which("vina") or "NOT FOUND"
    try:
        from app.tools.docking import VINA_CMD
        steps["VINA_CMD"] = VINA_CMD or "None"
    except Exception as e:
        steps["import_error"] = str(e)
    steps["tempdir"] = __import__("tempfile").gettempdir()
    steps["cwd"] = os.getcwd()
    return steps


@router.post("/run")
async def run_docking(req: DockingRequest, background_tasks: BackgroundTasks):
    if not req.pdb_id.strip() and not req.pdb_url.strip():
        raise HTTPException(400, detail="pdb_id or pdb_url is required")
    if not req.smiles.strip():
        raise HTTPException(400, detail="smiles is required")

    job_id = str(uuid.uuid4())
    _init(job_id, req)
    background_tasks.add_task(_worker, job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}")
@limiter.exempt
async def get_status(job_id: str):
    job = _read(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    return job


@router.get("/result/{job_id}/pdb", response_class=PlainTextResponse)
@limiter.exempt
async def get_pdb_result(job_id: str):
    job = _read(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    if job.get("status") != "complete":
        raise HTTPException(400, detail="Job not yet complete")
    result = job.get("result", {})
    ligand_pdb = result.get("ligand_pdb", "")
    if not ligand_pdb:
        raise HTTPException(404, detail="No ligand PDB available")
    return ligand_pdb
