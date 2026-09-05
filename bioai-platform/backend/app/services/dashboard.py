"""Scientific Dashboard service (BioNexus 2.0, Component 15).

Aggregates live operational state for the admin/scientist dashboard:
- overall summary counts (experiments, benchmark runs, engines, datasets),
- the engine registry with describe() contracts,
- dataset library + user-uploaded custom datasets ("bring your own data"),
- recent benchmark runs for live observation.

Custom datasets are stored server-side as JSON file entries (ephemeral in a
Space deployment — the snapshot API is used for durable workspace copies).
"""

from __future__ import annotations

import json
import logging
import os
import re

from app.engines import ENGINES
from app.services.dataset_library import list_datasets

logger = logging.getLogger(__name__)

CUSTOM_DIR = os.environ.get("BIONEXUS_CUSTOM_DATA_DIR")
if not CUSTOM_DIR:
    CUSTOM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "custom")


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    return slug or f"dataset-{len(os.listdir(CUSTOM_DIR)) if os.path.isdir(CUSTOM_DIR) else 0}"


# --- Custom (user-uploaded) datasets --------------------------------------

def list_custom_datasets() -> list[dict]:
    if not os.path.isdir(CUSTOM_DIR):
        return []
    rows = []
    for fname in sorted(os.listdir(CUSTOM_DIR)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(CUSTOM_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
            rows.append({k: data.get(k) for k in ("name", "category", "type", "date", "version", "records_count", "description")})
        except Exception as e:
            logger.warning("Custom dataset %s read failed: %s", fname, e)
    return rows


def upload_custom_dataset(name: str, category: str, records: list, description: str = "") -> dict:
    """Persist a user-provided dataset as a JSON catalog entry. Returns its summary."""
    if not name.strip():
        raise ValueError("name is required")
    if not records:
        raise ValueError("records must be a non-empty list")
    os.makedirs(CUSTOM_DIR, exist_ok=True)
    slug = _slug(name)
    payload = {
        "name": slug,
        "category": category or "custom",
        "type": "user",
        "date": "2026-09-05",
        "version": 1,
        "records_count": len(records),
        "description": description,
        "records": records,
    }
    path = os.path.join(CUSTOM_DIR, f"{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return {k: payload[k] for k in ("name", "category", "type", "date", "version", "records_count", "description")}


# --- Aggregates ------------------------------------------------------------

def _count_supabase(table: str) -> int:
    try:
        from app.services.supabase import get_supabase
        resp = get_supabase().table(table).select("id", count="exact", head=True).execute()
        return resp.count or 0
    except Exception as e:
        logger.warning("supabase count(%s) failed: %s", table, e)
        return 0


def _recent_runs(limit: int = 10) -> list[dict]:
    try:
        from app.services.supabase import get_supabase
        resp = get_supabase().table("benchmark_runs").select("*").order("created_at", desc=True).limit(limit).execute()
        return resp.data or []
    except Exception as e:
        logger.warning("benchmark_runs list failed: %s", e)
        return []


def summary() -> dict:
    return {
        "experiments": _count_supabase("jobs"),
        "benchmark_runs": _count_supabase("benchmark_runs"),
        "datasets_catalog": len(list_datasets()),
        "datasets_user": len(list_custom_datasets()),
        "engines": len(ENGINES),
        "engines_by_name": sorted(ENGINES.keys()),
    }


def engine_status() -> list[dict]:
    rows = []
    for name in sorted(ENGINES):
        engine = ENGINES[name]
        desc = engine.describe()
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


def datasets_list() -> dict:
    return {"catalog": list_datasets(), "user": list_custom_datasets(), "count": len(list_datasets()) + len(list_custom_datasets())}


def recent_runs(limit: int = 10) -> dict:
    return {"runs": _recent_runs(limit), "limit": limit}