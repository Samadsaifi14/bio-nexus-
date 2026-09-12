"""Authenticated scientific dashboard routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import require_user_id
from app.services.dashboard import (
    datasets_list,
    engine_status,
    recent_runs,
    summary,
    upload_custom_dataset,
)

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/summary")
async def dashboard_summary(user_id: str = Depends(require_user_id)):
    return summary(user_id)


@router.get("/api/dashboard/engines")
async def dashboard_engines(user_id: str = Depends(require_user_id)):
    return {"engines": engine_status()}


@router.get("/api/dashboard/datasets")
async def dashboard_datasets(user_id: str = Depends(require_user_id)):
    return datasets_list(user_id)


@router.get("/api/dashboard/runs")
async def dashboard_runs(user_id: str = Depends(require_user_id)):
    return recent_runs(user_id)


class UploadDataRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="custom", max_length=80)
    description: str = Field(default="", max_length=2000)
    records: list[dict] = Field(min_length=1, max_length=10_000)


@router.post("/api/dashboard/upload_data")
async def dashboard_upload(body: UploadDataRequest, user_id: str = Depends(require_user_id)):
    """Store a caller-owned custom dashboard dataset in tenant-scoped storage."""
    try:
        entry = upload_custom_dataset(user_id, body.name, body.category, body.records, body.description)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Dataset storage is unavailable") from exc
    return {
        "status": "stored",
        "dataset": entry,
        "note": "Custom dashboard data is private to the authenticated account. Use a controlled export workflow for durable publication artifacts.",
    }
