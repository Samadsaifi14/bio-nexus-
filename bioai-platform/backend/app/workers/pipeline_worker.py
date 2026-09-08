"""
Background pipeline worker: picks up queued jobs and runs the v2 pipeline
using asyncio.create_task (in-process). Status is PATCHed to Supabase via
raw HTTP so we never import app.db.
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import httpx

from app.config import settings
from app.routers.pipeline_v2 import run_pipeline

logger = logging.getLogger(__name__)

_supabase_url = settings.SUPABASE_URL.rstrip("/")
_supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY

_HEADERS = {
    "apikey": _supabase_key,
    "Authorization": f"Bearer {_supabase_key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

_client: httpx.AsyncClient | None = None
_client_loop_id: int | None = None


def _get_client() -> httpx.AsyncClient:
    global _client, _client_loop_id
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    current_id = id(current_loop)
    if _client is None or _client.is_closed or _client_loop_id != current_id:
        _client = httpx.AsyncClient(timeout=30)
        _client_loop_id = current_id
    return _client


def _public_error(exc: Exception) -> str:
    """Return a stable user-facing error without leaking backend/provider details."""
    text = str(exc).lower()
    if "blast" in text or "ncbi" in text or "ebi" in text:
        return "BLAST could not complete with the external sequence-search providers. Please retry the analysis."
    if "timeout" in text or "timed out" in text:
        return "The analysis took longer than expected. Please retry in a few minutes."
    if "uniprot" in text or "mapping" in text:
        return "Protein annotation could not be completed for this result. Please retry the analysis."
    return "The analysis could not be completed. Please retry."


async def _patch(table: str, job_id: str, payload: dict) -> None:
    url = f"{_supabase_url}/rest/v1/{table}?id=eq.{job_id}"
    resp = await _get_client().patch(url, headers=_HEADERS, json=payload)
    resp.raise_for_status()


async def _fetch_job(table: str, job_id: str) -> dict | None:
    url = f"{_supabase_url}/rest/v1/{table}?id=eq.{job_id}&select=*"
    resp = await _get_client().get(url, headers=_HEADERS)
    if resp.status_code != 200:
        return None
    rows = resp.json()
    return rows[0] if rows else None


async def _heartbeat(table: str, job_id: str, stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            await asyncio.sleep(120)
            if stop_event.is_set():
                break
            now = datetime.datetime.utcnow().isoformat()
            url = f"{_supabase_url}/rest/v1/{table}?id=eq.{job_id}"
            try:
                await _get_client().patch(url, headers=_HEADERS, json={"claimed_at": now})
            except Exception as exc:
                logger.warning("Heartbeat PATCH failed for job %s: %s", job_id, type(exc).__name__)
    except asyncio.CancelledError:
        pass


async def process_job(job_id: str) -> None:
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
            logger.error("Job %s not found", job_id)
            return

        # IMPORTANT: query_preview is display-only and is intentionally truncated.
        # Never execute scientific analysis from it. Prefer the immutable full
        # sequence stored in context_json / query_sequence / query.
        ctx = job.get("context_json")
        if isinstance(ctx, str):
            import json as _json
            try:
                ctx = _json.loads(ctx)
            except Exception:
                ctx = None

        query = ""
        if isinstance(ctx, dict):
            query = ctx.get("sequence", "") or (ctx.get("query") or {}).get("sequence", "")
        if not query:
            query = job.get("query_sequence") or job.get("query") or ""
        # Legacy rows may only contain query_preview. Keep this last-resort path
        # for compatibility, but do not silently treat a truncated preview as a
        # complete sequence when the row advertises a larger sequence length.
        if not query:
            preview = job.get("query_preview", "") or ""
            expected_len = 0
            if isinstance(ctx, dict):
                expected_len = int(ctx.get("length") or (ctx.get("query") or {}).get("length") or 0)
            if expected_len and len(preview) < expected_len:
                raise RuntimeError("Full query sequence is unavailable for this job")
            query = preview
        if not query:
            raise RuntimeError("Full query sequence is unavailable for this job")

        organism = job.get("organism", "Homo sapiens")
        analysis_type = job.get("analysis_type", "comprehensive")

        fast_mode = False
        blast_params: dict = {}
        if isinstance(ctx, dict):
            fast_mode = ctx.get("fast_mode", False)
            blast_params = {
                "database": ctx.get("database", ""),
                "program": ctx.get("program", ""),
                "max_hits": ctx.get("max_hits", 100),
                "query_accession": ctx.get("query_accession", ""),
            }

        async def _status_cb(new_status: str):
            try:
                await _patch("jobs", job_id, {"status": new_status})
            except Exception:
                logger.debug("Status callback PATCH failed for job %s", job_id)

        result = await run_pipeline(
            query,
            organism=organism,
            analysis_type=analysis_type,
            status_callback=_status_cb,
            fast_mode=fast_mode,
            blast_params=blast_params,
            job_id=job_id,
        )

        done_at = datetime.datetime.utcnow().isoformat()
        from app.services.artifact_storage import upload_json
        storage_url = upload_json(job_id, "context", result)

        await _patch("jobs", job_id, {
            "status": "complete",
            "storage_url": storage_url,
            "result": None,
            "completed_at": done_at,
            "error": None,
            "error_message": None,
        })

    except Exception as exc:
        # Full traceback stays in server logs; only a concise safe message reaches UX.
        logger.exception("Pipeline failed for job %s", job_id)
        public_error = _public_error(exc)
        try:
            await _patch("jobs", job_id, {
                "status": "failed",
                "error": public_error,
                "error_message": public_error,
            })
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
    asyncio.ensure_future(process_job(job_id))
