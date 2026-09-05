"""Continuous Paper Generation routes (Component 18).

- POST /api/experiments/{job_id}/paper/regenerate   — render one new version now.
- GET  /api/experiments/{job_id}/paper/versions     — artifact version list.
- GET  /api/experiments/{job_id}/paper/latest       — latest version (journal query).
- POST /api/paper/continuous                        — subscribe journal for interval.
- GET  /api/paper/continuous/subscriptions          — active subscriptions.
- POST /api/paper/continuous/tick                   — trigger due regenerations now.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_user_id
from app.services.paper_artifacts import (
    build_artifact,
    latest_artifact,
    list_artifacts,
    read_artifact_text,
    subscribe,
    subscriptions,
    tick,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["paper"])


@router.post("/api/experiments/{job_id}/paper/regenerate")
async def paper_regenerate(job_id: str, user_id: str | None = Depends(get_user_id)):
    try:
        manifest = build_artifact(job_id, "bmc")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "rendered", "version": manifest}


@router.get("/api/experiments/{job_id}/paper/versions")
async def paper_versions(job_id: str, user_id: str | None = Depends(get_user_id)):
    return {"job_id": job_id, "versions": list_artifacts(job_id)}


@router.get("/api/experiments/{job_id}/paper/latest")
async def paper_latest(job_id: str, journal: str = "bmc", user_id: str | None = Depends(get_user_id)):
    manifest = latest_artifact(job_id, journal)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No artifact for this job/journal")
    return {"version": manifest, "content": read_artifact_text(job_id, manifest)}


class ContinuousRequest(BaseModel):
    job_id: str
    journal: str = "bmc"
    interval_seconds: int = 300


@router.post("/api/paper/continuous")
async def paper_continuous(body: ContinuousRequest, user_id: str | None = Depends(get_user_id)):
    try:
        return subscribe(body.job_id, body.journal, body.interval_seconds)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/api/paper/continuous/subscriptions")
async def paper_continuous_subscriptions(user_id: str | None = Depends(get_user_id)):
    return {"subscriptions": subscriptions()}


@router.post("/api/paper/continuous/tick")
async def paper_continuous_tick(user_id: str | None = Depends(get_user_id)):
    produced = tick()
    return {"regenerated": produced, "count": len(produced)}