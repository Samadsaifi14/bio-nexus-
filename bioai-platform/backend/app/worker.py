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

# Load OpenMM's native libraries BEFORE any rdkit import. The OpenMM and
# RDKit wheels bundle conflicting copies of MSVC runtime DLLs
# (msvcp140/concrt140); if rdkit loads first, OpenMM's Context creation
# crashes with a native access violation. ADMET/docking jobs import rdkit
# lazily, so preloading openmm here guarantees safe ordering for MD jobs.
try:
    import openmm.app  # noqa: F401
except Exception:  # pragma: no cover - openmm may be absent in some envs
    pass

from app.config import settings
from app.services.supabase import get_client

logger = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
POLL_INTERVAL = 3  # seconds
# Long-running scientific jobs legitimately exceed a few minutes.  Keep the
# reclaim window above the longest normal provider budget (BLAST ~65 min) and
# use bounded attempts below so a dead worker is retried without looping
# forever.  This also matches durable-worker-design.md.
DEFAULT_STUCK_JOB_TIMEOUT_MIN = 90
STUCK_JOB_TIMEOUT_MIN = DEFAULT_STUCK_JOB_TIMEOUT_MIN  # backwards-compatible name
STUCK_JOB_TIMEOUT_BY_TABLE = {
    "jobs": 90,
    "docking_jobs": 90,
    "sequencing_jobs": 90,
    "ngs_jobs": 90,
}
SWEEP_EVERY = 20  # sweep every N poll ticks (~60s)

# Per-type concurrency caps
MAX_CONCURRENT = {
    "docking": 2,
    "sequencing": 1,
    "pipeline": 1,
    "md": 1,
    "function_predict": 1,
    "ngs": 1,
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


# Tables that carry an updated_at column. The jobs table does NOT have one
# (migration 005_worker_durable only adds claimed_at/claimed_by/attempts/
# max_attempts to jobs), so a PATCH touching updated_at on it is rejected by
# PostgREST and silently leaves the job queued forever. Only mention the column
# for tables that actually define it.
_TABLES_WITH_UPDATED_AT = {"docking_jobs", "sequencing_jobs", "ngs_jobs"}


def _claim_direct(table: str, worker_id: str) -> dict | None:
    """Fallback: claim a queued job via direct Supabase queries (no RPC needed)."""
    import httpx
    # 1. Find a queued job (order by id as fallback if created_at is missing)
    url = f"{_base()}/rest/v1/{table}?status=eq.queued&attempts=lt.3&order=id.asc&limit=1&select=*"
    resp = httpx.get(url, headers=_headers(), timeout=15)
    if resp.status_code != 200:
        logger.warning("Direct claim query failed for %s: %s %s", table, resp.status_code, resp.text[:200])
        return None
    rows = resp.json()
    if not rows:
        return None
    job = rows[0]
    # 2. Claim it with an atomic update (only if still queued)
    now = datetime.now(timezone.utc).isoformat()
    patch_url = f"{_base()}/rest/v1/{table}?id=eq.{job['id']}&status=eq.queued"
    patch_body = {
        "status": "running",
        "claimed_at": now,
        "claimed_by": worker_id,
        "attempts": (job.get("attempts") or 0) + 1,
    }
    if table in _TABLES_WITH_UPDATED_AT:
        patch_body["updated_at"] = now
    resp = httpx.patch(patch_url, headers=_headers(), json=patch_body, timeout=15)
    if resp.status_code != 200:
        logger.warning("Direct claim PATCH failed for %s %s: %s %s", table, job["id"], resp.status_code, resp.text[:200])
        return None
    updated = resp.json()
    if isinstance(updated, list) and updated:
        return updated[0]
    return None


def _patch(table: str, job_id: str, payload: dict) -> None:
    import httpx
    url = f"{_base()}/rest/v1/{table}?id=eq.{job_id}"
    httpx.patch(url, headers=_headers(), json=payload, timeout=15)


def _stale_recovery_payload(table: str, row: dict) -> dict:
    """Return a bounded recovery action for a stale worker claim.

    A stale claim is infrastructure failure, not scientific failure.  Requeue
    while retry budget remains; only become terminal after max_attempts.
    """
    attempts = int(row.get("attempts") or 0)
    max_attempts = int(row.get("max_attempts") or 3)
    previous = row.get("status", "unknown")
    if attempts < max_attempts:
        return {
            "status": "queued",
            "claimed_at": None,
            "claimed_by": None,
            "error": f"Recovered stale worker claim (was {previous}); retrying with a fresh worker",
        }

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "status": "failed",
        "claimed_at": None,
        "claimed_by": None,
        "error": f"Worker recovery exhausted after {attempts} attempt(s) (was {previous})",
    }
    if table == "jobs":
        payload["completed_at"] = now
    else:
        payload["done_at"] = now
    return payload


# Table -> (claim RPC name) mirroring _DISPATCH below. The pipeline table is
# special-cased: its claim RPC is named claim_next_pipeline_job, not derived
# from the table name.
_TABLE_TO_RPC = {
    "jobs": "claim_next_pipeline_job",
    "docking_jobs": "claim_next_docking_job",
    "sequencing_jobs": "claim_next_sequencing_job",
    "ngs_jobs": "claim_next_ngs_job",
}


def _claim_rcp_sql(table: str) -> str:
    """Build a claim RPC definition for a queued-job table (mirrors migrations)."""
    rpc_name = _TABLE_TO_RPC[table]
    updated_at = ", updated_at=now()" if table in _TABLES_WITH_UPDATED_AT else ""
    return f"""CREATE OR REPLACE FUNCTION {rpc_name}(worker_id text)
RETURNS {table} LANGUAGE plpgsql SECURITY DEFINER AS $do$
DECLARE job {table};
BEGIN
  SELECT * INTO job FROM {table} WHERE status = 'queued' AND attempts < max_attempts
  ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF job.id IS NOT NULL THEN
    UPDATE {table} SET status='running', claimed_at=now(), claimed_by=worker_id,
    attempts=attempts+1{updated_at} WHERE id = job.id RETURNING * INTO job;
  END IF;
  RETURN job;
END; $do$;"""


def _ensure_claim_rpcs() -> None:
    """Best-effort: create any missing claim RPCs so queued jobs are always claimable.

    The claim RPCs live in backend/migrations/005_worker_durable.sql and
    007_ngs_jobs.sql, but those migrations may not have been applied to a
    deployed Supabase project. The polling loop already falls back to
    ``_claim_direct`` when an RPC is absent; self-healing the RPC here restores
    the reliable atomic claim path (FOR UPDATE SKIP LOCKED) so jobs cannot get
    stuck in ``queued`` just because a migration was never run.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase not configured — cannot ensure claim RPCs")
        return
    try:
        import httpx
        api = f"{_base()}/rest/v1/rpc/exec_sql"
        # Ensure the worker-tracking columns exist first. The claim RPCs and the
        # direct-claim fallback both filter on `attempts`/`max_attempts`, so if
        # migration 005_worker_durable.sql was never applied to this project the
        # jobs table would lack those columns and no claim could ever succeed —
        # leaving every job stuck in "queued". Re-apply the column adds
        # idempotently before creating the RPCs.
        col_sql = (
            "ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS claimed_at timestamptz, "
            "ADD COLUMN IF NOT EXISTS claimed_by text, "
            "ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0, "
            "ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3, "
            "ADD COLUMN IF NOT EXISTS updated_at timestamptz"
        )
        for table in _TABLE_TO_RPC:
            try:
                col_resp = httpx.post(api, headers=_headers(), json={"query": col_sql.format(table=table)}, timeout=20)
                if col_resp.status_code == 200:
                    logger.info("Ensured worker-tracking columns for %s", table)
                else:
                    logger.warning("Worker-tracking column ensure for %s returned %s: %s",
                                   table, col_resp.status_code, col_resp.text[:200])
            except Exception as exc:
                logger.warning("Worker-tracking column ensure for %s failed: %s", table, exc)
        for table in _TABLE_TO_RPC:
            for attempt in range(2):
                try:
                    resp = httpx.post(api, headers=_headers(), json={"query": _claim_rcp_sql(table)}, timeout=20)
                    if resp.status_code == 200:
                        logger.info("Ensured claim RPC %s for %s", _TABLE_TO_RPC[table], table)
                        break
                    logger.warning("Claim RPC ensure for %s returned %s (attempt %d): %s",
                                   table, resp.status_code, attempt + 1, resp.text[:200])
                except Exception as exc:
                    logger.warning("Claim RPC ensure for %s failed (attempt %d): %s", table, attempt + 1, exc)
    except Exception as exc:
        logger.warning("Failed to ensure claim RPCs (exec_sql may be disabled): %s", exc)


def _sweep_stuck(table: str) -> int:
    """Recover jobs whose worker claim has stopped receiving heartbeats.

    The timeout is deliberately longer than normal provider budgets. A stale
    row is requeued while retry budget remains and is failed only after bounded
    attempts are exhausted. This prevents a healthy long BLAST/MD/NGS run from
    being declared dead after a few minutes and prevents infinite retry loops.
    """
    import httpx
    from datetime import timedelta

    timeout_min = STUCK_JOB_TIMEOUT_BY_TABLE.get(table, DEFAULT_STUCK_JOB_TIMEOUT_MIN)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=timeout_min)).isoformat()
    url = (
        f"{_base()}/rest/v1/{table}"
        f"?status=not.in.(complete,failed)"
        f"&claimed_at=lt.{cutoff}"
        f"&select=id,status,attempts,max_attempts"
    )
    resp = httpx.get(url, headers=_headers(), timeout=15)
    if resp.status_code != 200:
        return 0
    stuck = resp.json()
    count = 0
    for row in stuck:
        _patch(table, row["id"], _stale_recovery_payload(table, row))
        count += 1
    if count:
        logger.warning("Recovered %d stale job(s) from %s", count, table)
    return count


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------

def _run_docking(job: dict) -> None:
    if not job or not job.get("id"):
        logger.warning("Skipping dispatch of phantom job (no id): %s", job)
        return
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


def _run_ngs(job: dict) -> None:
    import asyncio
    from app.routers.ngs import _worker as ngs_worker
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ngs_worker(job["id"]))
    except Exception as exc:
        logger.exception("Worker NGS error for %s", job["id"])
        _handle_failure("ngs_jobs", job, exc)
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
    pdb_id = payload.get("pdb_id", "").upper().strip()
    mode = payload.get("mode", "minimize")

    if not pdb_id or len(pdb_id) != 4:
        _handle_failure("docking_jobs", job, ValueError(f"Invalid PDB ID: {pdb_id!r}"))
        return

    try:
        logger.info("Running MD simulation: PDB=%s mode=%s", pdb_id, mode)
        result = run_simulation(
            pdb_id,
            mode,
            platform=payload.get("platform"),
            forcefield=payload.get("forcefield"),
            solvent=payload.get("solvent"),
            run_length_ps=payload.get("run_length_ps"),
        )

        # AI interpretation (best-effort, never blocks)
        try:
            import asyncio
            from app.ai.tool_interpreter import interpret_tool_result
            ai_interp = asyncio.run(interpret_tool_result("md", result))
            if ai_interp:
                result["ai_interpretation"] = ai_interp
        except Exception:
            pass

        from app.services.artifact_storage import upload_json
        storage_url = upload_json(job["id"], "result", result)
        supabase = get_client()
        supabase.table("docking_jobs").update({
            "status": "complete",
            "storage_url": storage_url,
            "result_sdf": None,
        }).eq("id", job["id"]).execute()
        logger.info("MD simulation complete for %s (engine=%s)", pdb_id, result.get("engine", "unknown"))
    except Exception as exc:
        logger.exception("Worker MD error for %s", pdb_id)
        _handle_failure("docking_jobs", job, exc)


def _run_function_predict(job: dict) -> None:
    from app.tools.function_predict import predict_function
    from app.services.supabase import get_client
    payload = {**job, **(job.get("payload") or {})}
    pdb_id = payload.get("pdb_id", "")
    try:
        result = predict_function(pdb_id)

        # AI interpretation (best-effort, never blocks)
        try:
            import asyncio
            from app.ai.tool_interpreter import interpret_tool_result
            ai_interp = asyncio.run(interpret_tool_result("function_predict", result))
            if ai_interp:
                result["ai_interpretation"] = ai_interp
        except Exception:
            pass

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
    job_id = (job.get("id") or "") if isinstance(job, dict) else ""
    attempts = job.get("attempts", 0) if isinstance(job, dict) else 0
    max_attempts = job.get("max_attempts", 3) if isinstance(job, dict) else 3
    ref = job_id[:8] if job_id else "unknown"
    error_msg = f"Job failed: {exc}. Reference ID: {ref}"
    if not job_id:
        logger.error("Cannot handle failure — job id is empty: %s", exc)
        return
    if attempts >= max_attempts:
        now = datetime.now(timezone.utc).isoformat()
        payload = {"status": "failed", "error": error_msg}
        if table != "jobs":
            payload["done_at"] = now
        _patch(table, job_id, payload)
    else:
        _patch(table, job_id, {
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
    "ngs_jobs": ("claim_next_ngs_job", _run_ngs, "ngs"),
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
        if not job or not job.get("id"):
            # Fallback: try direct claim when RPC is missing
            try:
                job = _claim_direct(table, WORKER_ID)
            except Exception as exc:
                logger.exception("Direct claim failed for %s: %s", table, exc)
                job = None
        if not job or not job.get("id"):
            continue
        logger.info("Claimed %s job %s", table, job["id"])

        async def _exec(j=job, r=runner, s=sem):
            async with s:
                await asyncio.to_thread(r, j)

        asyncio.create_task(_exec())


async def _loop() -> None:
    global _shutdown
    logger.info("Worker started: id=%s polling every %ds", WORKER_ID, POLL_INTERVAL)
    # Self-heal missing claim RPCs once before polling so queued jobs are always
    # claimable via the atomic path (not just the direct-update fallback).
    try:
        await asyncio.to_thread(_ensure_claim_rpcs)
    except Exception:
        logger.exception("Failed to ensure claim RPCs at worker start")
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
