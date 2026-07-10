from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.deps import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docking", tags=["docking"])

_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PERSIST_FILE = os.path.join(_PERSIST_DIR, "jobs_docking.json")
_MAX_JOBS = 200
_JOB_TTL = 7200


def _load_jobs() -> dict[str, dict]:
    if os.path.exists(_PERSIST_FILE):
        try:
            with open(_PERSIST_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load jobs from {_PERSIST_FILE}: {e}")
    return {}


def _save_jobs() -> None:
    try:
        os.makedirs(_PERSIST_DIR, exist_ok=True)
        with open(_PERSIST_FILE, "w") as f:
            json.dump(_jobs, f, default=str)
    except Exception as e:
        logger.warning(f"Failed to save jobs: {e}")


def _prune_jobs() -> None:
    now = time.time()
    stale = [
        jid
        for jid, j in list(_jobs.items())
        if (j.get("done_at") and (now - j["done_at"]) > _JOB_TTL)
        or (j.get("status") in ("complete", "failed") and len(_jobs) > _MAX_JOBS)
    ]
    for jid in stale:
        _jobs.pop(jid, None)
    if stale:
        _save_jobs()


_jobs: dict[str, dict] = _load_jobs()
_lock = threading.Lock()


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
    created_at: float = 0.0
    done_at: Optional[float] = None


def _init(job_id: str, req: DockingRequest) -> None:
    with _lock:
        _prune_jobs()
        _jobs[job_id] = {
            "job_id":    job_id,
            "pdb_id":    req.pdb_id,
            "pdb_url":   req.pdb_url,
            "smiles":    req.smiles,
            "status":    "queued",
            "result":    None,
            "error":     None,
            "created_at": time.time(),
            "done_at":   None,
        }
        _save_jobs()


def _patch(job_id: str, **kw) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)
            _save_jobs()


def _read(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


async def _worker(job_id: str) -> None:
    job = _read(job_id)
    if not job:
        return
    _patch(job_id, status="preparing")

    from app.tools.docking import DockingTool

    tool = DockingTool()
    params: dict = {"smiles": job["smiles"]}
    if job.get("pdb_url"):
        params["pdb_url"] = job["pdb_url"]
    if job.get("pdb_id"):
        params["pdb_id"] = job["pdb_id"]
    result = await tool.run(params)

    if "error" in result and not result.get("poses"):
        _patch(job_id, status="failed", error=result["error"], done_at=time.time())
    else:
        _patch(job_id, status="complete", result=result, done_at=time.time())


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
