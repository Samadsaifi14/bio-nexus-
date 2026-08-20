from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from app.deps import limiter
from app.services.supabase import get_supabase
from app.services.auth import require_user_id
from app.services.ssrf import validate_url
from app.services.rate_limit import check_daily_limit_ngs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ngs", tags=["ngs"])

_TABLE = "ngs_jobs"
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


class NGSRequest(BaseModel):
    fastq_url: str
    reference: str = "sars-cov-2"


class NGSJob(BaseModel):
    job_id: str
    fastq_url: str
    reference: str
    status: str = "queued"
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""
    done_at: Optional[str] = None


def _init(job_id: str, req: NGSRequest, user_id: str) -> None:
    try:
        _prune_jobs()
    except Exception:
        pass
    _ensure_ngs_table()
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


_table_initialized = False

def _ensure_ngs_table() -> None:
    """Ensure ngs_jobs table has created_at column and the claim RPC exists."""
    global _table_initialized
    if _table_initialized:
        return
    _table_initialized = True
    try:
        import httpx as _httpx
        from app.config import settings
        base = settings.SUPABASE_URL.rstrip("/")
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}

        # Add created_at column if missing
        sql = "ALTER TABLE ngs_jobs ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();"
        resp = _httpx.post(f"{base}/rest/v1/rpc/exec_sql", headers=headers, json={"query": sql}, timeout=15)
        if resp.status_code == 200:
            logger.info("ngs_jobs: added created_at column")

        # Create the claim RPC
        rpc_sql = """CREATE OR REPLACE FUNCTION claim_next_ngs_job(worker_id text)
RETURNS ngs_jobs LANGUAGE plpgsql SECURITY DEFINER AS $do$
DECLARE job ngs_jobs;
BEGIN
  SELECT * INTO job FROM ngs_jobs WHERE status = 'queued' AND attempts < max_attempts
  ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF job.id IS NOT NULL THEN
    UPDATE ngs_jobs SET status='running', claimed_at=now(), claimed_by=worker_id,
    attempts=attempts+1, updated_at=now() WHERE id = job.id RETURNING * INTO job;
  END IF;
  RETURN job;
END; $do$;"""
        resp = _httpx.post(f"{base}/rest/v1/rpc/exec_sql", headers=headers, json={"query": rpc_sql}, timeout=15)
        if resp.status_code == 200:
            logger.info("ngs_jobs: created claim_next_ngs_job RPC")
    except Exception as e:
        logger.debug("Auto-migration skipped (exec_sql not available): %s", e)


def _patch(job_id: str, **kw) -> None:
    get_supabase().table(_TABLE).update(kw).eq("id", job_id).execute()


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


async def _worker(job_id: str) -> None:
    job = _read(job_id)
    if not job:
        return
    _patch(job_id, status="running")

    from app.tools.ngs import NGSPipeline, PIPELINE_TIMEOUT

    tool = NGSPipeline()
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
        from app.services.artifact_storage import upload_json
        storage_url = upload_json(job_id, "result", result)
        _patch(job_id, status="complete", storage_url=storage_url, result=None, done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))


VALID_DEMO = {"synthetic", "demo", "test"}


@router.post("/run")
async def run_ngs(request: Request, req: NGSRequest, user_id: str = Depends(require_user_id)):
    await check_daily_limit_ngs(request)

    if not req.fastq_url.strip():
        raise HTTPException(400, detail="fastq_url is required")
    if req.fastq_url.lower() not in VALID_DEMO:
        if not req.fastq_url.startswith(("http://", "https://")):
            raise HTTPException(400, detail="fastq_url must be a valid URL or 'synthetic' for demo data")
        validate_url(req.fastq_url)

    job_id = str(uuid.uuid4())
    _init(job_id, req, user_id)
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
    from app.tools.ngs import REFERENCE_URLS
    return {
        "references": [
            {"id": k, "name": k.replace("-", " ").title()}
            for k in REFERENCE_URLS
        ]
    }
