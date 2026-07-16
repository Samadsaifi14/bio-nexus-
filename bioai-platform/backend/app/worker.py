"""
Durable job worker — polls Supabase for queued jobs, claims them atomically
via FOR UPDATE SKIP LOCKED RPCs, executes, and retries on failure.

Run as a separate container:
    python -m app.worker

Or as an in-process task (less durable):
    from app.worker import start_worker
    await start_worker()  # in a FastAPI lifespan
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import signal
from datetime import datetime, timezone

from app.config import settings
from app.services.supabase import get_client

logger = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
POLL_INTERVAL = 3  # seconds
STUCK_JOB_TIMEOUT_MIN = 10
SWEEP_EVERY = 20  # sweep every N poll ticks (~60s)

# Per-type concurrency caps
MAX_CONCURRENT = {
    "docking": 2,
    "sequencing": 1,
    "pipeline": 1,
    "md": 1,
    "function_predict": 1,
}

_semaphore: dict[str, asyncio.Semaphore] = {}
_shutdown = False


def _sem(typ: str) -> asyncio.Semaphore:
    if typ not in _semaphore:
        _semaphore[typ] = asyncio.Semaphore(MAX_CONCURRENT[typ])
    return _semaphore[typ]


# ---------------------------------------------------------------------------
# Supabase helpers (raw HTTP for RPC calls + patches)
# ---------------------------------------------------------------------------

def _headers():
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base():
    return settings.SUPABASE_URL.rstrip("/")


def _rpc(fn: str, worker_id: str) -> dict | None:
    """Call a Supabase RPC and return the first row, or None."""
    import httpx
    url = f"{_base()}/rest/v1/rpc/{fn}"
    resp = httpx.post(url, headers=_headers(), json={"worker_id": worker_id}, timeout=15)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if isinstance(data, list):
        return data[0] if data else None
    return data if data else None


def _patch(table: str, job_id: str, payload: dict) -> None:
    import httpx
    url = f"{_base()}/rest/v1/{table}?id=eq.{job_id}"
    httpx.patch(url, headers=_headers(), json=payload, timeout=15)


def _sweep_stuck(table: str) -> int:
    """Reclaim jobs stuck in 'running' for longer than STUCK_JOB_TIMEOUT_MIN."""
    import httpx
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STUCK_JOB_TIMEOUT_MIN)).isoformat()
    url = (
        f"{_base()}/rest/v1/{table}"
        f"?status=eq.running&claimed_at=lt.{cutoff}"
        f"&select=id"
    )
    resp = httpx.get(url, headers=_headers(), timeout=15)
    if resp.status_code != 200:
        return 0
    stuck = resp.json()
    count = 0
    for row in stuck:
        _patch(table, row["id"], {
            "status": "queued",
            "claimed_at": None,
            "claimed_by": None,
        })
        count += 1
    if count:
        logger.warning("Sweep reclaimed %d stuck job(s) from %s", count, table)
    return count


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------

def _run_docking(job: dict) -> None:
    payload = {**job, **(job.get("payload") or {})}
    tool_type = payload.get("tool_type", "docking")

    if tool_type == "md":
        _run_md(job)
    elif tool_type == "function_predict":
        _run_function_predict(job)
    else:
        from app.routers.docking import _run_docking_sync
        try:
            _run_docking_sync(job["id"], payload)
        except Exception as exc:
            logger.exception("Worker docking error for %s", job["id"])
            _handle_failure("docking_jobs", job, exc)


def _run_sequencing(job: dict) -> None:
    import asyncio
    from app.routers.sequencing import _worker as seq_worker
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(seq_worker(job["id"]))
    except Exception as exc:
        logger.exception("Worker sequencing error for %s", job["id"])
        _handle_failure("sequencing_jobs", job, exc)
    finally:
        loop.close()


def _run_pipeline(job: dict) -> None:
    from app.workers.pipeline_worker import process_job
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(process_job(job["id"]))
    except Exception as exc:
        logger.exception("Worker pipeline error for %s", job["id"])
        _handle_failure("jobs", job, exc)
    finally:
        loop.close()


def _run_md(job: dict) -> None:
    from app.tools.md_sim import run_simulation
    from app.services.supabase import get_client
    payload = {**job, **(job.get("payload") or {})}
    pdb_id = payload.get("pdb_id", "")
    mode = payload.get("mode", "minimize")
    try:
        result = run_simulation(pdb_id, mode)
        from app.services.artifact_storage import upload_json
        storage_url = upload_json(job["id"], "result", result)
        supabase = get_client()
        supabase.table("docking_jobs").update({
            "status": "complete",
            "storage_url": storage_url,
            "result_sdf": None,
        }).eq("id", job["id"]).execute()
    except Exception as exc:
        logger.exception("Worker MD error for %s", job["id"])
        _handle_failure("docking_jobs", job, exc)


def _run_function_predict(job: dict) -> None:
    from app.tools.function_predict import predict_function
    from app.services.supabase import get_client
    payload = {**job, **(job.get("payload") or {})}
    pdb_id = payload.get("pdb_id", "")
    try:
        result = predict_function(pdb_id)
        from app.services.artifact_storage import upload_json
        storage_url = upload_json(job["id"], "result", result)
        supabase = get_client()
        supabase.table("docking_jobs").update({
            "status": "complete",
            "storage_url": storage_url,
            "result_sdf": None,
        }).eq("id", job["id"]).execute()
    except Exception as exc:
        logger.exception("Worker function prediction error for %s", job["id"])
        _handle_failure("docking_jobs", job, exc)


def _handle_failure(table: str, job: dict, exc: Exception) -> None:
    """Requeue if under max_attempts, else mark failed permanently."""
    attempts = job.get("attempts", 0)
    max_attempts = job.get("max_attempts", 3)
    error_msg = "Job failed. Reference ID: " + job["id"][:8]
    if attempts >= max_attempts:
        now = datetime.now(timezone.utc).isoformat()
        payload = {"status": "failed", "error": error_msg}
        if table != "jobs":
            payload["done_at"] = now
        _patch(table, job["id"], payload)
    else:
        _patch(table, job["id"], {
            "status": "queued",
            "claimed_at": None,
            "claimed_by": None,
        })


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

_DISPATCH = {
    "docking_jobs": ("claim_next_docking_job", _run_docking, "docking"),
    "sequencing_jobs": ("claim_next_sequencing_job", _run_sequencing, "sequencing"),
    "jobs": ("claim_next_pipeline_job", _run_pipeline, "pipeline"),
}


async def _poll_once(sweep_counter: int) -> None:
    if sweep_counter % SWEEP_EVERY == 0:
        for table in _DISPATCH:
            try:
                _sweep_stuck(table)
            except Exception:
                logger.exception("Sweep failed for %s", table)

    for table, (rpc_fn, runner, typ) in _DISPATCH.items():
        sem = _sem(typ)
        if sem.locked():
            continue
        job = _rpc(rpc_fn, WORKER_ID)
        if job is None:
            continue
        logger.info("Claimed %s job %s", table, job["id"])

        async def _exec(j=job, r=runner, s=sem):
            async with s:
                await asyncio.to_thread(r, j)

        asyncio.create_task(_exec())


async def _loop() -> None:
    global _shutdown
    logger.info("Worker started: id=%s polling every %ds", WORKER_ID, POLL_INTERVAL)
    sweep_counter = 0
    while not _shutdown:
        sweep_counter += 1
        try:
            await _poll_once(sweep_counter)
        except Exception:
            logger.exception("Poll cycle error")
        await asyncio.sleep(POLL_INTERVAL)
    logger.info("Worker shutting down")


def _handle_signal(sig, frame):
    global _shutdown
    logger.info("Received signal %s — shutting down gracefully", sig)
    _shutdown = True


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def start_worker() -> asyncio.Task:
    """Launch worker as an in-process background task (4.2a)."""
    return asyncio.create_task(_loop())


def main():
    """Standalone worker entrypoint (4.2b): python -m app.worker"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
