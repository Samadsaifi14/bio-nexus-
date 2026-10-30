"""Register analysis-tool jobs in the shared ``jobs`` table.

The Jobs and History pages of the frontend read ``GET /api/jobs`` (routers/jobs.py),
which selects from the Supabase ``jobs`` table. Historically only the BLAST
pipeline (routers/pipelines.py) and the wizard (routers/pipeline_v2.py) wrote
there, so every other tool was invisible in job history even though it produced
real background work. This module gives each tool router a tiny, uniform API to
record its runs in that same table.

Design constraints
------------------
* **Ownership.** Every row carries the authenticated ``user_id`` the router
  already resolved (``require_user_id`` / optional ``get_user_id``). Anonymous
  runs are simply not recorded — history is per-user.
* **Never fatal.** A registry outage must not fail the analysis the user is
  waiting on. Every write is best-effort, off-thread, and swallow-all.
* **Small payloads.** Tool routers keep authoritative results in their own
  stores (docking_jobs, storage, in-memory mirrors). The registry row only
  carries a bounded summary so ``context_json`` never balloons.
* **Completion via ``propagate_patch``.** Routers and workers already funnel
  every status change through a local ``_patch``-style helper; one hook line per
  module completes the registry row without touching business logic.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# One writer keeps order stable (matches app/services/job_state.py pattern).
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job-registry")

# Bounded summary so the shared table never receives docking poses or trees.
_MAX_CONTEXT_CHARS = 24_000

# Registry rows may only carry statuses the router/jobs.py surface understands.
_RUNNING_SERVERAliases = frozenset({
    "queued", "running", "downloading", "submitted_to_ncbi", "polling_ncbi",
    "parsing", "interpreting", "fetching_uniprot", "running_msa",
    "fetching_alphafold", "structure_ready", "queued_models", "selected_models",
    "modelising", "refining", "plotting",
})
_SUCCESS_ALIASES = frozenset({"complete", "completed"})
_ERROR_ALIASES = frozenset({"failed", "error", "interrupted", "cancelled"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client():
    try:
        from app.services.supabase import get_supabase

        return get_supabase()
    except Exception as exc:  # pragma: no cover - config/import failure
        logger.debug("job registry unavailable: %s", exc)
        return None


def _shrink(context: dict[str, Any] | None) -> dict[str, Any]:
    """Keep a bounded, JSON-safe summary. Oversized values describe themselves."""
    if not isinstance(context, dict):
        return {}
    try:
        encoded = __import__("json").dumps(context, default=str)
    except Exception:
        return {"_note": "summary not serialisable"}
    if len(encoded) <= _MAX_CONTEXT_CHARS:
        return context
    return {
        "_truncated": True,
        "_original_chars": len(encoded),
        "status": context.get("status"),
        "error": context.get("error"),
        "storage_url": context.get("storage_url"),
    }


def _submit(fn, *args, **kwargs) -> None:
    """Run one registry write on the mirror thread; never raise into the caller.

    Preserve keyword arguments: registry writers such as _insert_row and
    _finish_row expose keyword-only fields (query_preview, context, status).
    """
    try:
        _pool.submit(_guarded, fn, *args, **kwargs)
    except RuntimeError:
        # Interpreter shutdown: write inline so the final state is not lost.
        _guarded(fn, *args, **kwargs)


def _guarded(fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.debug("job registry write skipped", exc_info=True)


def _insert_row(
    job_id: str,
    tool: str,
    user_id: str,
    *,
    query_preview: str = "",
    status: str = "running",
    context: dict[str, Any] | None = None,
    parent_job_id: str | None = None,
) -> None:
    client = _client()
    if client is None or not user_id or not job_id:
        return
    payload: dict[str, Any] = {
        "id": job_id,
        "user_id": user_id,
        "tool": tool,
        "query_preview": (query_preview or "")[:120],
        "status": status,
        "pipeline_type": tool,
        "steps_completed": [],
        "context_json": _shrink({"source": tool, **(context or {})}),
        "progress_pct": 0,
        "created_at": _now(),
        "completed_at": None,
        "error": None,
    }
    if parent_job_id:
        payload["parent_job_id"] = parent_job_id
    client.table("jobs").insert(payload).execute()


def _finish_row(
    job_id: str,
    *,
    status: str,
    context: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    client = _client()
    if client is None or not job_id:
        return
    payload: dict[str, Any] = {
        "status": status,
        "progress_pct": 100 if status == "complete" else None,
        "completed_at": _now(),
    }
    if error is not None:
        payload["error"] = str(error)[:500]
    if context:
        # Merge onto the existing summary instead of clobbering the submit-side
        # context the tool router already wrote.
        try:
            row = client.table("jobs").select("context_json").eq("id", job_id).limit(1).execute()
            merged = (row.data or [{}])[0].get("context_json") or {}
        except Exception:
            merged = {}
        if not isinstance(merged, dict):
            merged = {}
        merged.update(_shrink(context))
        payload["context_json"] = merged
    client.table("jobs").update(payload).eq("id", job_id).execute()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def new_job_id() -> str:
    return str(uuid.uuid4())


def start(
    tool: str,
    user_id: str | None,
    *,
    job_id: str | None = None,
    query_preview: str = "",
    context: dict[str, Any] | None = None,
    parent_job_id: str | None = None,
) -> str | None:
    """Record a run that is about to (or already does) execute in the background.

    Returns the job id actually registered — the caller-supplied one when given —
    or ``None`` when there is no authenticated user or the queue is unavailable.
    """
    if not user_id:
        return None
    rid = job_id or new_job_id()
    _submit(_insert_row, rid, tool, user_id, query_preview=query_preview,
            context=context, parent_job_id=parent_job_id)
    return rid


def record_completed(
    tool: str,
    user_id: str | None,
    *,
    query_preview: str = "",
    context: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """One-shot row for synchronous tools whose work ends inside the request."""
    if not user_id:
        return
    rid = new_job_id()
    status = "failed" if error else "complete"
    # Insert first (row must exist before the finish update makes sense). Both
    # writes go through the same single-thread executor, preserving that order.
    _submit(_insert_row, rid, tool, user_id, query_preview=query_preview, status=status)
    _submit(_finish_row, rid, status=status, context=context, error=error)


def finish(job_id: str, *, status: str, context: dict[str, Any] | None = None,
           error: str | None = None) -> None:
    """Move one registered row to a terminal state (idempotent update)."""
    normalized = _normalize_status(status)
    if normalized is None:
        return
    _submit(_finish_row, job_id, status=normalized, context=context, error=error)


def _normalize_status(status: Any) -> str | None:
    """Map a tool's own status vocabulary onto the shared ``jobs`` rules."""
    if not isinstance(status, str) or not status:
        return None
    if status in _RUNNING_SERVERAliases:
        return "running"
    if status in _SUCCESS_ALIASES:
        return "complete"
    if status in _ERROR_ALIASES:
        return "failed"
    return None


def propagate_patch(kind: str, job_id: str, patch: dict[str, Any]) -> None:
    """Mirror a tool router's ``_patch``-style status change into the registry.

    Call this at the end of a router's local ``_patch(job_id, **kw)`` helper (or
    the worker's terminal writes for tool rows that only the worker touches).
    Only keys carrying status meaning ("status" / "phase" / "error") matter;
    everything else is ignored, so it is safe to pass the whole patch.
    """
    if not job_id:
        return
    status = patch.get("status") if isinstance(patch, dict) else None
    phase = patch.get("phase") if isinstance(patch, dict) else None
    normalized = _normalize_status(status)
    if normalized is None and phase is not None:
        normalized = _normalize_status(phase)
    if normalized is None:
        return  # progress-only patch; the row stays as-is
    context: dict[str, Any] = {"kind": kind}
    if isinstance(patch, dict):
        if patch.get("storage_url"):
            context["storage_url"] = patch["storage_url"]
        if patch.get("newick"):
            context["tree_preview"] = str(patch["newick"])[:400]
        if patch.get("pdb_text"):
            context["has_structure"] = True
    error = patch.get("error") if isinstance(patch, dict) else None
    _submit(_finish_row, job_id, status=normalized, context=context, error=error)
