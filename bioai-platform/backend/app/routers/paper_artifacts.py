"""Versioned paper-artifact routes.

Paper artifacts are derived from private experiment results. Every job-specific route
requires the owning user. The background regeneration daemon is deployment-controlled;
a public HTTP request cannot trigger regeneration for other users' subscriptions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import require_user_id
from app.services.job_access import owns_job
from app.services.paper_artifacts import (
    build_artifact,
    latest_artifact,
    list_artifacts,
    read_artifact_text,
    subscribe,
    subscriptions,
)

router = APIRouter(tags=["paper"])


def _require_owned_job(job_id: str, user_id: str) -> None:
    if not owns_job(job_id, user_id):
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/api/experiments/{job_id}/paper/regenerate")
async def paper_regenerate(job_id: str, user_id: str = Depends(require_user_id)):
    _require_owned_job(job_id, user_id)
    try:
        manifest = build_artifact(job_id, "bmc")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Experiment context is unavailable") from exc
    return {"status": "rendered", "version": manifest}


@router.get("/api/experiments/{job_id}/paper/versions")
async def paper_versions(job_id: str, user_id: str = Depends(require_user_id)):
    _require_owned_job(job_id, user_id)
    return {"job_id": job_id, "versions": list_artifacts(job_id)}


@router.get("/api/experiments/{job_id}/paper/latest")
async def paper_latest(
    job_id: str,
    journal: str = "bmc",
    user_id: str = Depends(require_user_id),
):
    _require_owned_job(job_id, user_id)
    manifest = latest_artifact(job_id, journal)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No artifact for this job/journal")
    return {"version": manifest, "content": read_artifact_text(job_id, manifest)}


class ContinuousRequest(BaseModel):
    job_id: str
    journal: str = "bmc"
    interval_seconds: int = Field(default=300, ge=60, le=86400)


@router.post("/api/paper/continuous")
async def paper_continuous(
    body: ContinuousRequest,
    user_id: str = Depends(require_user_id),
):
    _require_owned_job(body.job_id, user_id)
    try:
        return subscribe(body.job_id, body.journal, body.interval_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/paper/continuous/subscriptions")
async def paper_continuous_subscriptions(user_id: str = Depends(require_user_id)):
    """Return only subscriptions whose jobs are owned by the caller."""
    visible = {
        job_id: values
        for job_id, values in subscriptions().items()
        if owns_job(job_id, user_id)
    }
    return {"subscriptions": visible}


@router.post("/api/paper/continuous/tick")
async def paper_continuous_tick(user_id: str = Depends(require_user_id)):
    """Manual global ticks are disabled; the opt-in deployment daemon owns scheduling."""
    raise HTTPException(status_code=403, detail="Manual continuous-paper ticks are disabled through the public API")
