from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sequencing", tags=["sequencing"])

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


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
    created_at: float = 0.0
    done_at: Optional[float] = None


def _init(job_id: str, req: SequencingRequest) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id":    job_id,
            "fastq_url": req.fastq_url,
            "reference": req.reference,
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
    _patch(job_id, status="downloading")

    from app.tools.sequencing import SequencingPipeline

    tool = SequencingPipeline()
    result = await tool.run({
        "fastq_url": job["fastq_url"],
        "reference": job["reference"],
    })

    if "error" in result and not result.get("steps_completed"):
        _patch(job_id, status="failed", error=result["error"], done_at=time.time())
    else:
        _patch(job_id, status="complete", result=result, done_at=time.time())


@router.post("/run")
async def run_sequencing(req: SequencingRequest, background_tasks: BackgroundTasks):
    if not req.fastq_url.strip():
        raise HTTPException(400, detail="fastq_url is required")
    if not req.fastq_url.startswith(("http://", "https://")):
        raise HTTPException(400, detail="fastq_url must be a valid URL")

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


@router.get("/references")
async def list_references():
    from app.tools.sequencing import REFERENCE_URLS
    return {
        "references": [
            {"id": k, "name": k.replace("-", " ").title()}
            for k in REFERENCE_URLS
        ]
    }
