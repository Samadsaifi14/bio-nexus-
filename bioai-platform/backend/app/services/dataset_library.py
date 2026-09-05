"""Research Dataset Library (BioNexus 2.0, Component 14).

A versioned, typed collection of curated reference datasets that engines can
snapshot into their run-specific data folders, keeping benchmark/engine runs
reproducible and independent of live upstream databases.

Catalog is data entries under app/data/datasets/ (index.json lists summaries;
<name>.json holds the records). A snapshot is an immutable copy into a
target workspace directory, with a manifest recording source version, type and
ingestion date.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "datasets")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def list_datasets() -> list[dict]:
    """Return dataset summaries from the index (no record payloads)."""
    index_path = os.path.join(DATASETS_DIR, "index.json")
    try:
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
        datasets = index.get("datasets") or []
        return [{k: d.get(k) for k in ("name", "category", "type", "date", "version", "records_count", "description", "citation")} for d in datasets]
    except Exception as e:
        logger.warning("Dataset index read failed: %s", e)
        return []


def get_dataset(name: str) -> Optional[dict]:
    """Return the full dataset (records included) or None."""
    path = os.path.join(DATASETS_DIR, f"{name}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Dataset %s read failed: %s", name, e)
        return None


def snapshot_dataset(name: str, target_dir: str) -> dict:
    """Copy a dataset's records + manifest into target_dir (created if needed).

    Returns a snapshot summary with the manifest path. Raises ValueError when
    the dataset is unknown or the target cannot be prepared.
    """
    dataset = get_dataset(name)
    if dataset is None:
        raise ValueError(f"unknown dataset '{name}'")
    os.makedirs(target_dir, exist_ok=True)

    records_path = os.path.join(target_dir, f"{name}_records.json")
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump(dataset.get("records") or [], f, indent=2)

    manifest = {
        "dataset": name,
        "source_version": dataset.get("version"),
        "type": dataset.get("type"),
        "date": dataset.get("date"),
        "category": dataset.get("category"),
        "record_count": len(dataset.get("records") or []),
        "snapshotted_at": _iso_now(),
    }
    manifest_path = os.path.join(target_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {"dataset": name, "record_count": manifest["record_count"], "target": target_dir,
            "records_path": records_path, "manifest_path": manifest_path,
            "snapshotted_at": manifest["snapshotted_at"]}