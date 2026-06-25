from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.deps import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sequencing", tags=["sequencing"])

_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PERSIST_FILE = os.path.join(_PERSIST_DIR, "jobs_sequencing.json")
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
        _prune_jobs()
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
        _patch(job_id, status="failed", error="Pipeline timed out", done_at=time.time())
        return

    if "error" in result and not result.get("steps_completed"):
        _patch(job_id, status="failed", error=result["error"], done_at=time.time())
    else:
        _patch(job_id, status="complete", result=result, done_at=time.time())


VALID_DEMO = {"synthetic", "demo", "test"}


@router.post("/run")
async def run_sequencing(req: SequencingRequest, background_tasks: BackgroundTasks):
    if not req.fastq_url.strip():
        raise HTTPException(400, detail="fastq_url is required")
    if not req.fastq_url.startswith(("http://", "https://")) and req.fastq_url.lower() not in VALID_DEMO:
        raise HTTPException(400, detail="fastq_url must be a valid URL or 'synthetic' for demo data")

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


@router.get("/references")
async def list_references():
    from app.tools.sequencing import REFERENCE_URLS
    return {
        "references": [
            {"id": k, "name": k.replace("-", " ").title()}
            for k in REFERENCE_URLS
        ]
    }
