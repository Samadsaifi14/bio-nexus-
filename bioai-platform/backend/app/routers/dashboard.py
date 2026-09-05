"""Scientific Dashboard routes (Component 15).

Live admin surface for scientists:
- GET /api/dashboard/summary          — headline counts.
- GET /api/dashboard/engines          — registered engines + contracts.
- GET /api/dashboard/datasets         — catalog + user-uploaded datasets.
- GET /api/dashboard/runs             — recent benchmark runs (live).
- POST /api/dashboard/upload_data     — ingest a user's own dataset (BYO data).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_user_id
from app.services.dashboard import (
    datasets_list,
    engine_status,
    recent_runs,
    summary,
    upload_custom_dataset,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/summary")
async def dashboard_summary(user_id: str | None = Depends(get_user_id)):
    return summary()


@router.get("/api/dashboard/engines")
async def dashboard_engines(user_id: str | None = Depends(get_user_id)):
    return {"engines": engine_status()}


@router.get("/api/dashboard/datasets")
async def dashboard_datasets(user_id: str | None = Depends(get_user_id)):
    return datasets_list()


@router.get("/api/dashboard/runs")
async def dashboard_runs(user_id: str | None = Depends(get_user_id)):
    return recent_runs()


class UploadDataRequest(BaseModel):
    name: str
    category: str = "custom"
    description: str = ""
    records: list[dict] = []


@router.post("/api/dashboard/upload_data")
async def dashboard_upload(body: UploadDataRequest, user_id: str | None = Depends(get_user_id)):
    """Ingest a scientist's own dataset file into the dashboard library."""
    try:
        entry = upload_custom_dataset(body.name, body.category, body.records, body.description)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"storage failure: {e}")
    return {"status": "stored", "dataset": entry,
            "note": "user uploads are session-scoped on ephemeral deployments; snapshot them for durable copies."}