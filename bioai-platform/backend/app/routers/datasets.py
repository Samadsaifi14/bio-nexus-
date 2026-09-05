"""Research Dataset Library routes (Component 14).

- GET /api/datasets                 — list versioned curated datasets (summaries).
- GET /api/datasets/{name}          — full dataset payload (records included).
- POST /api/datasets/{name}/snapshot — snapshot records + manifest into a target
                                       workspace directory for engine runs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_user_id
from app.services.dataset_library import (
    get_dataset,
    list_datasets,
    snapshot_dataset,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["datasets"])


@router.get("/api/datasets")
async def datasets_list(user_id: str | None = Depends(get_user_id)):
    """Summaries of every dataset in the library."""
    datasets = list_datasets()
    return {"datasets": datasets, "count": len(datasets)}


@router.get("/api/datasets/{name}")
async def datasets_get(name: str, user_id: str | None = Depends(get_user_id)):
    """One full dataset (records included)."""
    dataset = get_dataset(name)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{name}'")
    return dataset


class SnapshotRequest(BaseModel):
    target_dir: str


@router.post("/api/datasets/{name}/snapshot")
async def datasets_snapshot(name: str, body: SnapshotRequest,
                            user_id: str | None = Depends(get_user_id)):
    """Copy a dataset (records + manifest) into an engine workspace folder."""
    if not body.target_dir.strip():
        raise HTTPException(status_code=422, detail="target_dir is required")
    try:
        snap = snapshot_dataset(name, body.target_dir)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"target_dir not usable: {e}")
    return snap