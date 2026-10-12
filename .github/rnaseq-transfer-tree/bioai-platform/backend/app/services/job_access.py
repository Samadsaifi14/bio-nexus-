"""Owner-scoped access to private BioNexus job records and result context.

The backend Supabase client uses a service-role credential and bypasses row-level
security. User-facing routes therefore must include ``user_id`` in every job query
rather than fetch by UUID and check ownership afterwards.

Public sharing is intentionally handled elsewhere through explicit share tokens.
"""
from __future__ import annotations

from typing import Any

from app.services.supabase import get_supabase

_RESULT_SECTIONS = (
    "blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment",
    "alphafold", "interpret", "docking", "md", "ngs", "rnaseq",
)


def fetch_owned_job(job_id: str, user_id: str, fields: str = "*") -> dict[str, Any] | None:
    """Return one job only when it belongs to ``user_id``."""
    try:
        result = (
            get_supabase().table("jobs")
            .select(fields)
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return dict(result.data[0]) if result.data else None
    except Exception:
        return None


def fetch_owned_job_context(job_id: str, user_id: str) -> dict[str, Any] | None:
    """Return private scientific context after an owner-scoped database match.

    Inline ``context_json`` is returned when it already contains result sections.
    Otherwise an offloaded artifact is hydrated only after ownership is established.
    Input-only context is returned as a last resort for incomplete/queued jobs.
    """
    row = fetch_owned_job(job_id, user_id, "context_json,storage_url")
    if not row:
        return None

    inline = row.get("context_json")
    if isinstance(inline, dict) and any(key in inline for key in _RESULT_SECTIONS):
        return inline

    storage_url = row.get("storage_url")
    if storage_url:
        from app.services.artifact_storage import download_json

        hydrated = download_json(storage_url)
        if isinstance(hydrated, dict):
            return hydrated

    return inline if isinstance(inline, dict) else None


def owns_job(job_id: str, user_id: str) -> bool:
    """Cheap ownership predicate for routes that operate on derived local artifacts."""
    return fetch_owned_job(job_id, user_id, "id") is not None
