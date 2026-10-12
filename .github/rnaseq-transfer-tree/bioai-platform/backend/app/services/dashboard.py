"""Scientific dashboard aggregation with tenant-scoped custom datasets."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from app.engines import ENGINES
from app.services.dataset_library import list_datasets

logger = logging.getLogger(__name__)

CUSTOM_ROOT = Path(
    os.environ.get("BIONEXUS_CUSTOM_DATA_DIR")
    or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "custom")
).resolve()


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    return slug[:96] or "dataset"


def _user_dir(user_id: str) -> Path:
    # Supabase user ids are UUID strings, but sanitize again before using a path.
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "", user_id)[:128]
    if not safe_user:
        raise ValueError("invalid user id")
    path = (CUSTOM_ROOT / safe_user).resolve()
    path.relative_to(CUSTOM_ROOT)
    return path


# --- Custom (user-uploaded) datasets --------------------------------------
def list_custom_datasets(user_id: str) -> list[dict]:
    folder = _user_dir(user_id)
    if not folder.is_dir():
        return []
    rows: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            rows.append({
                key: data.get(key)
                for key in ("name", "category", "type", "date", "version", "records_count", "description")
            })
        except Exception:
            logger.warning("Custom dataset read failed", exc_info=True)
    return rows


def upload_custom_dataset(
    user_id: str,
    name: str,
    category: str,
    records: list,
    description: str = "",
) -> dict:
    """Persist a caller-owned custom dataset in a tenant-specific directory."""
    if not name.strip():
        raise ValueError("name is required")
    if not records:
        raise ValueError("records must be a non-empty list")
    if len(records) > 10_000:
        raise ValueError("records exceeds the 10,000-row dashboard upload limit")

    folder = _user_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    payload = {
        "name": slug,
        "category": category or "custom",
        "type": "user",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "version": 1,
        "records_count": len(records),
        "description": description[:2000],
        "records": records,
    }
    path = folder / f"{slug}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return {
        key: payload[key]
        for key in ("name", "category", "type", "date", "version", "records_count", "description")
    }


# --- Aggregates ------------------------------------------------------------
def _count_owned_jobs(user_id: str) -> int:
    try:
        from app.services.supabase import get_supabase

        response = (
            get_supabase().table("jobs")
            .select("id", count="exact", head=True)
            .eq("user_id", user_id)
            .execute()
        )
        return response.count or 0
    except Exception:
        logger.warning("Owned job count failed", exc_info=True)
        return 0


def _recent_owned_benchmark_runs(user_id: str, limit: int = 10) -> list[dict]:
    """Return benchmark runs only for jobs owned by the caller.

    The benchmark_runs schema stores job_id, so resolve the caller's recent job ids
    first rather than returning the global research ledger.
    """
    try:
        from app.services.supabase import get_supabase

        sb = get_supabase()
        jobs = sb.table("jobs").select("id").eq("user_id", user_id).limit(500).execute().data or []
        job_ids = [row["id"] for row in jobs if row.get("id")]
        if not job_ids:
            return []
        response = (
            sb.table("benchmark_runs")
            .select("*")
            .in_("job_id", job_ids)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        logger.warning("Owned benchmark run list failed", exc_info=True)
        return []


def summary(user_id: str) -> dict:
    custom = list_custom_datasets(user_id)
    return {
        "experiments": _count_owned_jobs(user_id),
        "datasets_catalog": len(list_datasets()),
        "datasets_user": len(custom),
        "engines": len(ENGINES),
        "engines_by_name": sorted(ENGINES.keys()),
        "scope": "authenticated_user",
    }


def engine_status() -> list[dict]:
    rows = []
    for name in sorted(ENGINES):
        desc = ENGINES[name].describe()
        rows.append({
            "name": name,
            "version": desc.get("version"),
            "tool": desc.get("tool"),
            "databases": desc.get("databases"),
            "export_formats": desc.get("export_formats"),
            "benchmarks": desc.get("benchmarks"),
            "citations": len(desc.get("citations") or []),
        })
    return rows


def datasets_list(user_id: str) -> dict:
    catalog = list_datasets()
    custom = list_custom_datasets(user_id)
    return {"catalog": catalog, "user": custom, "count": len(catalog) + len(custom)}


def recent_runs(user_id: str, limit: int = 10) -> dict:
    limit = max(1, min(limit, 50))
    return {"runs": _recent_owned_benchmark_runs(user_id, limit), "limit": limit}
