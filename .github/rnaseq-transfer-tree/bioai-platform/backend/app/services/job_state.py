"""Durable mirror for in-process background jobs.

``phylo``, ``pipeline_v2`` and ``structure_predict`` execute work in a background
task and keep their state in a module-level dict. That state is the only copy of a
job's progress and results, so any container restart -- a deploy, a scale-down, or
a crash -- silently destroyed it and the client's next poll returned 404 for a job
that had merely been interrupted.

This module writes that same state to ``transient_jobs`` so a restart can restore
what completed and reconcile what did not.

Deliberate limits
-----------------
* **Not a work queue.** Nothing is claimed or resumed. A restart kills the
  subprocess doing the work, so pretending otherwise would let a job report
  progress it is not making. Non-terminal rows are reconciled to ``interrupted``
  and the user re-runs deliberately.
* **Never fatal.** Durability is a side effect of a job the user is waiting on, so
  a Supabase outage, missing credentials, or a missing migration must degrade to
  in-memory behaviour rather than fail the job. Every error here is swallowed and
  logged.
* **Bounded mirror size.** Payloads for phylogenetics can be large (alignments,
  Newick trees). Values beyond the cap are truncated with a marker rather than
  stored in full; the authoritative copy is still the in-memory dict.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

# Mirror writes are offloaded to a single background thread. They are a Supabase
# round-trip, and the callers are async request handlers and background jobs that
# patch their state many times per run; writing inline would block the event loop
# for the duration of every write. One worker keeps writes ordered, so the last
# state a job reached is the last one stored.
_mirror_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job-mirror")

# Statuses that need no reconciliation: the job already reached an outcome.
TERMINAL_STATUSES = frozenset({"complete", "completed", "failed", "error", "interrupted", "cancelled"})

# Cap the mirrored payload. Large enough for real phylogeny/structure results,
# small enough that a mirror write never becomes the slow part of a job.
MAX_STATE_CHARS = 256_000

# A job mirror that is this old is a restart artifact from a previous deploy and
# no longer worth carrying. Reconciliation still marks it interrupted; it is only
# dropped later, by the retention sweep.
RETENTION_DAYS = 14


def _client():
    """Return a Supabase client, or ``None`` when durability is unavailable."""
    try:
        if not _supabase_configured():
            return None
        from app.services.supabase import get_supabase

        return get_supabase()
    except Exception as exc:  # pragma: no cover - configuration/import failure
        logger.debug("transient job mirror unavailable: %s", exc)
        return None


def _supabase_configured() -> bool:
    try:
        from app.config import settings

        return bool(getattr(settings, "SUPABASE_URL", "") and getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", ""))
    except Exception:
        return False


def _truncate(state: Any) -> tuple[Any, bool]:
    """Return ``(state, truncated)``, shrinking an oversized payload to fit."""
    try:
        encoded = json.dumps(state, default=str)
    except Exception:
        return {}, True
    if len(encoded) <= MAX_STATE_CHARS:
        return state, False
    return {
        "_truncated": True,
        "_original_chars": len(encoded),
        "status": state.get("status") if isinstance(state, dict) else None,
        "error": "Job state exceeded the durable-mirror size limit; re-run to reproduce full results.",
    }, True


def mirror(job_id: str, kind: str, state: dict[str, Any]) -> None:
    """Mirror a job's state without blocking the caller.

    This is the entry point for request handlers and background jobs. The write is
    best-effort and asynchronous; a slow or dead Supabase delays the mirror, never
    the job the user is waiting on.
    """
    if not job_id:
        return
    try:
        _mirror_pool.submit(save_job_state, job_id, kind, dict(state))
    except RuntimeError:
        # Interpreter shutdown: fall back to writing inline rather than losing the
        # final state of a job that is completing right now.
        save_job_state(job_id, kind, state)


def _derive_status(state: dict[str, Any]) -> str:
    """Read a job's terminal status under either convention.

    ``phylo`` tracks its lifecycle in ``phase`` (``complete`` / ``error``) and
    carries no ``status`` at all, while the other routers use ``status``. Both are
    mirrored so a job is never left looking unfinished after it actually finished.
    """
    status = state.get("status")
    if isinstance(status, str) and status:
        return status
    phase = state.get("phase")
    if phase == "complete":
        return "complete"
    if phase in ("error", "failed"):
        return "failed"
    return "running"


def save_job_state(job_id: str, kind: str, state: dict[str, Any]) -> None:
    """Mirror one job's state. Best-effort; never raises."""
    if not job_id:
        return
    client = _client()
    if client is None:
        return

    payload, truncated = _truncate(state)
    status = _derive_status(state)
    phase = state.get("phase")
    try:
        client.table("transient_jobs").upsert(
            {
                "job_id": job_id,
                "kind": kind,
                "status": status,
                "phase": str(phase) if phase is not None else None,
                "state": payload,
            },
            on_conflict="job_id",
        ).execute()
    except Exception as exc:
        logger.warning("could not mirror %s job %s: %s", kind, job_id, exc)
        return
    if truncated:
        logger.info("mirrored state for %s job %s was truncated", kind, job_id)


def _select_recent(kind: str, statuses: list[str], limit: int) -> list[dict[str, Any]]:
    client = _client()
    if client is None:
        return []
    try:
        result = (
            client.table("transient_jobs")
            .select("job_id,kind,status,phase,state,created_at,updated_at")
            .eq("kind", kind)
            .in_("status", statuses)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        logger.warning("could not read mirrored %s jobs: %s", kind, exc)
        return []
    return [dict(row) for row in (result.data or [])]


# Statuses whose results are still worth serving after a restart.
RESTORABLE_STATUSES = ["complete", "completed"]


def load_finished(kind: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return successfully finished jobs so their results survive a restart."""
    return _select_recent(kind, RESTORABLE_STATUSES, limit)


def load_unfinished(kind: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return jobs left in a non-terminal state, i.e. ones a restart interrupted."""
    client = _client()
    if client is None:
        return []
    try:
        result = (
            client.table("transient_jobs")
            .select("job_id,kind,status,phase,state,created_at,updated_at")
            .eq("kind", kind)
            .not_.in_("status", list(TERMINAL_STATUSES))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        logger.warning("could not read unfinished %s jobs: %s", kind, exc)
        return []
    return [dict(row) for row in (result.data or [])]


def mark_interrupted(job_id: str, kind: str, reason: str) -> None:
    """Record a job that a restart caught mid-flight as a terminal failure."""
    client = _client()
    if client is None:
        return
    try:
        state = {"status": "interrupted", "error": reason, "interrupted": True}
        client.table("transient_jobs").upsert(
            {"job_id": job_id, "kind": kind, "status": "interrupted", "phase": None, "state": state},
            on_conflict="job_id",
        ).execute()
    except Exception as exc:
        logger.warning("could not mark job %s interrupted: %s", job_id, exc)


def purge_expired() -> int:
    """Drop mirrors older than the retention window. Returns the row count."""
    client = _client()
    if client is None:
        return 0
    try:
        result = (
            client.table("transient_jobs")
            .delete()
            .lt("updated_at", f"now() - interval '{RETENTION_DAYS} days'")
            .execute()
        )
        return len(result.data or [])
    except Exception as exc:
        logger.warning("could not purge expired job mirrors: %s", exc)
        return 0


def reconcile_on_startup(kind: str, hydrate) -> int:
    """Restore finished jobs and fail the ones a restart interrupted.

    ``hydrate(job_id, state)`` repopulates the router's in-memory dict so a
    client's poll finds the job it started before the restart. Returns the number
    of jobs marked interrupted.
    """
    restored = 0
    for row in load_finished(kind):
        job_id = str(row.get("job_id") or "")
        state = row.get("state")
        if not job_id or not isinstance(state, dict) or state.get("_truncated"):
            # A truncated mirror cannot be served as a real result; leaving it out
            # is better than handing the client a payload we know is incomplete.
            continue
        hydrate(job_id, state)
        restored += 1
    if restored:
        logger.info("restored %d finished %s job(s) from the durable mirror", restored, kind)

    reason = "This job was interrupted by a server restart or deploy and did not finish. Please re-run it."
    interrupted: list[str] = []
    for row in load_unfinished(kind):
        job_id = str(row.get("job_id") or "")
        if not job_id:
            continue
        mark_interrupted(job_id, kind, reason)
        interrupted.append(job_id)
        hydrate(job_id, {"status": "interrupted", "error": reason, "interrupted": True, "phase": None})

    if interrupted:
        logger.warning(
            "marked %d %s job(s) interrupted by a restart: %s",
            len(interrupted),
            kind,
            ", ".join(interrupted[:5]),
        )
    purge_expired()
    return len(interrupted)
