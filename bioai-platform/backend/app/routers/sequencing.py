from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

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
        ids = [row["id"] for row in to_delete]
        if ids:
            sb.table(_TABLE).delete().in_("id", ids).execute()


class SequencingRequest(BaseModel):
    fastq_url: str
    reference: str = "sars-cov-2"
    min_depth: int = Field(10, ge=1, le=100000)
    min_base_quality: int = Field(20, ge=0, le=93)
    min_mapping_quality: int = Field(20, ge=0, le=255)
    allele_frequency: float = Field(0.50, gt=0.0, le=1.0)
    ambiguity_min_frequency: float = Field(0.20, gt=0.0, le=1.0)


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
        "id": job_id,
        "fastq_url": req.fastq_url,
        "reference": req.reference,
        "status": "queued",
        "user_id": user_id,
        "result": None,
        "error": None,
        "done_at": None,
    }).execute()


def _patch(job_id: str, **kwargs) -> None:
    get_supabase().table(_TABLE).update(kwargs).eq("id", job_id).execute()


def _read(job_id: str, user_id: str | None = None) -> dict | None:
    query = get_supabase().table(_TABLE).select("*").eq("id", job_id)
    if user_id:
        query = query.eq("user_id", user_id)
    rows = query.execute().data
    if not rows:
        return None
    job = dict(rows[0])
    if job.get("storage_url") and not job.get("result"):
        from app.services.artifact_storage import download_json
        result = download_json(job["storage_url"])
        if result:
            job["result"] = result
    return job


async def _worker(job_id: str, parameters: dict | None = None) -> None:
    job = _read(job_id)
    if not job:
        return
    _patch(job_id, status="downloading")

    from app.tools.sequencing import SequencingPipeline, PIPELINE_TIMEOUT
    from app.services.artifact_storage import upload_json

    payload = {
        "fastq_url": job["fastq_url"],
        "reference": job["reference"],
        "job_id": job_id,
        **(parameters or {}),
    }
    try:
        result = await asyncio.wait_for(SequencingPipeline().run(payload), timeout=PIPELINE_TIMEOUT)
    except asyncio.TimeoutError:
        _patch(
            job_id,
            status="failed",
            error="Pipeline timed out before a ScientificResult was emitted",
            done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        )
        return

    storage_url = None
    try:
        storage_url = upload_json(job_id, "result", result)
    except Exception:
        logger.exception("Could not persist sequencing ScientificResult")

    scientific_status = str(result.get("status", "FAILED"))
    if scientific_status == "FAILED":
        reason = str((result.get("validation") or {}).get("reason") or "Scientific processing failed")
        _patch(
            job_id,
            status="failed",
            storage_url=storage_url,
            result=None if storage_url else result,
            error=reason,
            done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        )
        return

    # DEGRADED is a completed job with an explicit degraded scientific state.
    _patch(
        job_id,
        status="complete",
        storage_url=storage_url,
        result=None if storage_url else result,
        error=None,
        done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
    )


VALID_DEMO = {"synthetic", "demo", "test"}


@router.post("/run")
async def run_sequencing(request: Request, req: SequencingRequest, user_id: str = Depends(require_user_id)):
    if not req.fastq_url.strip():
        raise HTTPException(400, detail="fastq_url is required")
    if req.fastq_url.lower() not in VALID_DEMO:
        if not req.fastq_url.startswith(("http://", "https://")):
            raise HTTPException(400, detail="fastq_url must be a valid URL or 'synthetic' for explicit demo data")
        validate_url(req.fastq_url)
    if req.ambiguity_min_frequency > req.allele_frequency:
        raise HTTPException(400, detail="ambiguity_min_frequency must be <= allele_frequency")

    job_id = str(uuid.uuid4())
    _init(job_id, req, user_id)
    # Durable worker dispatch reads the DB row; the in-process worker path can
    # also use these declared parameters when invoked by worker.py.
    return {
        "job_id": job_id,
        "status": "queued",
        "parameters": {
            "min_depth": req.min_depth,
            "min_base_quality": req.min_base_quality,
            "min_mapping_quality": req.min_mapping_quality,
            "allele_frequency": req.allele_frequency,
            "ambiguity_min_frequency": req.ambiguity_min_frequency,
        },
    }


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
            {"id": key, "name": key.replace("-", " ").title()}
            for key in REFERENCE_URLS
        ]
    }
