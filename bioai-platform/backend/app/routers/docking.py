from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docking", tags=["docking"])

# ─── In-memory store ──────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class DockingRequest(BaseModel):
    pdb_id: str
    smiles: str


class DockingJob(BaseModel):
    job_id: str
    pdb_id: str
    smiles: str
    status: str = "queued"
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = 0.0
    done_at: Optional[float] = None


def _init(job_id: str, req: DockingRequest) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id":    job_id,
            "pdb_id":    req.pdb_id,
            "smiles":    req.smiles,
            "status":    "queued",
            "result":    None,
            "error":     None,
            "created_at": time.time(),
            "done_at":   None,
        }


def _patch(job_id: str, **kw) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


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
    result = await tool.run({
        "pdb_id": job["pdb_id"],
        "smiles": job["smiles"],
    })

    if "error" in result and not result.get("poses"):
        _patch(job_id, status="failed", error=result["error"], done_at=time.time())
    else:
        _patch(job_id, status="complete", result=result, done_at=time.time())


@router.post("/run")
async def run_docking(req: DockingRequest, background_tasks: BackgroundTasks):
    if not req.pdb_id.strip():
        raise HTTPException(400, detail="pdb_id is required")
    if not req.smiles.strip():
        raise HTTPException(400, detail="smiles is required")

    job_id = str(uuid.uuid4())
    _init(job_id, req)
    background_tasks.add_task(_worker, job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = _read(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    return job
