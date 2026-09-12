"""Research Dataset Library routes."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import require_user_id
from app.services.dataset_library import (
    dataset_lineage,
    get_dataset,
    list_datasets,
    snapshot_dataset,
    validate_dataset,
)

router = APIRouter(tags=["datasets"])


@router.get("/api/datasets")
async def datasets_list():
    datasets = list_datasets()
    return {"datasets": datasets, "count": len(datasets)}


@router.get("/api/datasets/{name}")
async def datasets_get(name: str):
    dataset = get_dataset(name)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{name}'")
    return dataset


@router.get("/api/datasets/{name}/validate")
async def datasets_validate(name: str):
    result = validate_dataset(name)
    if result.get("checks") and not result["checks"][0].get("passed"):
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{name}'")
    return result


@router.get("/api/datasets/{name}/lineage")
async def datasets_lineage(name: str):
    result = dataset_lineage(name)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{name}'")
    return result


class SnapshotRequest(BaseModel):
    label: str = Field(default="snapshot", min_length=1, max_length=80)


def _snapshot_target(user_id: str, label: str) -> Path:
    """Build a server-controlled export path; callers never supply a filesystem path."""
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "", user_id)[:128]
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-")[:80]
    if not safe_user or not safe_label:
        raise HTTPException(status_code=422, detail="Invalid snapshot label")
    root = Path(os.getenv("BIONEXUS_DATASET_EXPORT_ROOT", "/tmp/bionexus-dataset-exports")).resolve()
    target = (root / safe_user / safe_label).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid snapshot target") from None
    return target


@router.post("/api/datasets/{name}/snapshot")
async def datasets_snapshot(
    name: str,
    body: SnapshotRequest,
    user_id: str = Depends(require_user_id),
):
    target = _snapshot_target(user_id, body.label)
    try:
        result = snapshot_dataset(name, str(target))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Dataset export storage is unavailable") from exc
    # Server paths are operational details; report only stable artifact metadata.
    return {
        "dataset": result["dataset"],
        "record_count": result["record_count"],
        "dataset_sha256": result["dataset_sha256"],
        "records_sha256": result["records_sha256"],
        "manifest_sha256": result["manifest_sha256"],
        "snapshotted_at": result["snapshotted_at"],
        "label": body.label,
    }
