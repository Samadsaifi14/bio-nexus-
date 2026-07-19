"""
Background pipeline worker: picks up queued jobs and runs the v2 pipeline
using asyncio.create_task (in-process).  Status is PATCHed to Supabase via
raw HTTP so we never import app.db.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os

import httpx

from app.config import settings
from app.routers.pipeline_v2 import run_pipeline

logger = logging.getLogger(__name__)

_supabase_url = settings.SUPABASE_URL.rstrip("/")
_supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY  # service key for server-side writes

_HEADERS = {
    "apikey": _supabase_key,
    "Authorization": f"Bearer {_supabase_key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Reusable async client (created lazily)
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30)
    return _client


async def _patch(table: str, job_id: str, payload: dict) -> None:
    url = f"{_supabase_url}/rest/v1/{table}?id=eq.{job_id}"
    await _get_client().patch(url, headers=_HEADERS, json=payload)


async def _fetch_job(table: str, job_id: str) -> dict | None:
    url = f"{_supabase_url}/rest/v1/{table}?id=eq.{job_id}&select=*"
    resp = await _get_client().get(url, headers=_HEADERS)
    if resp.status_code != 200:
        return None
    rows = resp.json()
    return rows[0] if rows else None


async def _heartbeat(table: str, job_id: str, stop_event: asyncio.Event) -> None:
    """Periodically touch claimed_at so the sweep doesn't reclaim us."""
    try:
        while not stop_event.is_set():
            await asyncio.sleep(120)
            if stop_event.is_set():
                break
            now = datetime.datetime.utcnow().isoformat()
            url = f"{_supabase_url}/rest/v1/{table}?id=eq.{job_id}"
            try:
                await _get_client().patch(
                    url, headers=_HEADERS,
                    json={"claimed_at": now},
                )
            except Exception:
                pass
    except asyncio.CancelledError:
        pass


async def process_job(job_id: str) -> None:
    """Mark a pipeline job as running, execute steps, PATCH results."""

    # Optimistic lock: set status -> running
    try:
        await _patch("jobs", job_id, {"status": "running"})
    except Exception:
        logger.exception("Failed to mark job %s as running", job_id)
        return

    stop_event = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat("jobs", job_id, stop_event))

    try:
        job = await _fetch_job("jobs", job_id)
        if job is None:
            logger.error("Job %s not found in Supabase", job_id)
            return

        query = job.get("query_preview", "") or ""

        if not query:
            ctx = job.get("context_json")
            if isinstance(ctx, str):
                import json as _json
                try:
                    ctx = _json.loads(ctx)
                except Exception:
                    ctx = None
            if isinstance(ctx, dict):
                query = ctx.get("sequence", "")

        if not query:
            query = job.get("query_sequence") or job.get("query") or ""
        organism = job.get("organism", "Homo sapiens")
        analysis_type = job.get("analysis_type", "comprehensive")

        result = await run_pipeline(query, organism=organism, analysis_type=analysis_type)

        done_at = datetime.datetime.utcnow().isoformat()

        # Offload large result to Supabase Storage
        from app.services.artifact_storage import upload_json
        storage_url = upload_json(job_id, "context", result)

        await _patch(
            "jobs",
            job_id,
            {
                "status": "complete",
                "storage_url": storage_url,
                "results": None,
                "completed_at": done_at,
            },
        )

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        fail_at = datetime.datetime.utcnow().isoformat()
        try:
            await _patch(
                "jobs",
                job_id,
                {"status": "failed", "error": str(exc)[:2000]},
            )
        except Exception:
            logger.exception("Also failed to PATCH failure for job %s", job_id)
    finally:
        stop_event.set()
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


def dispatch_job(job_id: str) -> None:
    """Fire-and-forget enqueue into the async event loop."""
    asyncio.ensure_future(process_job(job_id))
