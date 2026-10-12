"""Reproducibility Ledger and deposition-bundle routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import get_user_id
from app.services.reproducibility import enforce, get_ledger, record_carbon
from app.services.reproducibility_bundle import build_bundle

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reproducibility"])


@router.get("/api/experiments/{job_id}/ledger")
async def ledger_get(job_id: str, user_id: str | None = Depends(get_user_id)):
    ledger = get_ledger(job_id)
    if ledger is None:
        raise HTTPException(status_code=404, detail="No ledger for this job")
    return ledger


@router.get("/api/experiments/{job_id}/ledger/validate")
async def ledger_validate(job_id: str, user_id: str | None = Depends(get_user_id)):
    return {"job_id": job_id, **enforce(get_ledger(job_id))}


@router.get("/api/experiments/{job_id}/reproducibility-bundle")
async def reproducibility_bundle(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Generate Docker/Conda/pip/CITATION/RO-Crate/manifests/checksums metadata."""
    bundle = build_bundle(job_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return bundle


class RecordCarbonRequest(BaseModel):
    step: str
    input: object | None = None
    process: dict = Field(default_factory=dict)
    output: object | None = None


@router.post("/api/experiments/{job_id}/ledger")
async def ledger_record(job_id: str, body: RecordCarbonRequest,
                        user_id: str | None = Depends(get_user_id)):
    if not body.step.strip():
        raise HTTPException(status_code=422, detail="step is required")
    carbon = record_carbon(job_id, body.step, body.input, body.process, body.output)
    return {"recorded": carbon, "job_id": job_id}
