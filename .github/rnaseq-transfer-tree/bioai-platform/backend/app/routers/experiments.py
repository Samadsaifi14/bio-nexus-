from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.auth import require_user_id
from app.services.job_access import owns_job
from app.services.experiment import (
    archive_manifest,
    begin_experiment,
    build_fingerprint,
    compare_experiments,
    doi_export_metadata,
    get_experiment,
    get_experiment_by_id,
    persist_archive,
    search_experiments,
)
from app.services.provenance import trace_for_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class CloneExperimentRequest(BaseModel):
    new_job_id: str = Field(..., description="Existing owned job UUID for the cloned experiment version")
    sequence: str = Field(..., min_length=1, description="Original input sequence; checksum is verified against the source")
    parameters: dict | None = None


class DoiMetadataRequest(BaseModel):
    title: str | None = None
    creators: list[dict] | None = None


def _owned_experiment_for_job(job_id: str, user_id: str) -> dict:
    if not owns_job(job_id, user_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


def _owned_experiment_by_id(experiment_id: str, user_id: str) -> dict:
    exp = get_experiment_by_id(experiment_id)
    if not exp or not exp.get("job_id") or not owns_job(str(exp["job_id"]), user_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.get("")
async def list_experiments(
    limit: int = Query(20, ge=1, le=200),
    q: str | None = None,
    pipeline: str | None = None,
    status: str | None = None,
    user_id: str = Depends(require_user_id),
):
    """Return only reproducibility records attached to jobs owned by the caller."""
    try:
        # The experiment service pre-dates tenant ownership. Filter its bounded
        # result set through the authoritative owned-job predicate before display.
        candidates = search_experiments(query=q, pipeline=pipeline, status=status, limit=200)
        visible = [exp for exp in candidates if exp.get("job_id") and owns_job(str(exp["job_id"]), user_id)]
        return {"experiments": visible[:limit]}
    except Exception:
        logger.warning("Experiments list degraded", exc_info=True)
        return {"experiments": [], "degraded": True}


@router.get("/id/{experiment_id}")
async def get_experiment_by_experiment_id(experiment_id: str, user_id: str = Depends(require_user_id)):
    return {"experiment": _owned_experiment_by_id(experiment_id, user_id)}


@router.get("/compare/{left_experiment_id}/{right_experiment_id}")
async def compare(
    left_experiment_id: str,
    right_experiment_id: str,
    user_id: str = Depends(require_user_id),
):
    left = _owned_experiment_by_id(left_experiment_id, user_id)
    right = _owned_experiment_by_id(right_experiment_id, user_id)
    return compare_experiments(left, right)


@router.get("/{job_id}")
async def get_experiment_by_job(job_id: str, user_id: str = Depends(require_user_id)):
    return {"experiment": _owned_experiment_for_job(job_id, user_id)}


@router.get("/{job_id}/provenance")
async def get_provenance(job_id: str, user_id: str = Depends(require_user_id)):
    exp = _owned_experiment_for_job(job_id, user_id)
    return trace_for_job(job_id, exp["experiment_id"])


@router.get("/{job_id}/archive")
async def get_archive(
    job_id: str,
    persist: bool = False,
    user_id: str = Depends(require_user_id),
):
    exp = _owned_experiment_for_job(job_id, user_id)
    return persist_archive(job_id) if persist else archive_manifest(exp)


@router.post("/{job_id}/doi-metadata")
async def build_doi_metadata(
    job_id: str,
    request: DoiMetadataRequest,
    user_id: str = Depends(require_user_id),
):
    exp = _owned_experiment_for_job(job_id, user_id)
    return doi_export_metadata(exp, title=request.title, creators=request.creators)


@router.post("/{job_id}/clone")
async def clone_experiment(
    job_id: str,
    request: CloneExperimentRequest,
    user_id: str = Depends(require_user_id),
):
    source = _owned_experiment_for_job(job_id, user_id)
    if not owns_job(request.new_job_id, user_id):
        raise HTTPException(status_code=404, detail="Target job not found")
    candidate = build_fingerprint(request.sequence, request.parameters or source.get("parameters") or {})
    if candidate["input_hash"] != source.get("input_hash"):
        raise HTTPException(status_code=409, detail="Clone rejected: supplied sequence does not match source input checksum")
    experiment_id = begin_experiment(
        request.new_job_id,
        request.sequence,
        source.get("pipeline") or "cloned",
        request.parameters or source.get("parameters") or {},
        parent_experiment_id=source["experiment_id"],
    )
    if not experiment_id:
        raise HTTPException(status_code=500, detail="Experiment clone could not be registered")
    return {"experiment_id": experiment_id, "parent_experiment_id": source["experiment_id"]}


@router.post("/{job_id}/finalize")
async def finalize(job_id: str, status: str, error: str | None = None):
    """Worker-only mutation: public finalization is deliberately disabled."""
    raise HTTPException(status_code=403, detail="Experiment finalization is worker-controlled")


@router.post("/debug/new")
async def debug_new():
    raise HTTPException(status_code=404, detail="Debug experiment endpoints are disabled")


@router.post("/debug/trace")
async def debug_trace():
    raise HTTPException(status_code=404, detail="Debug experiment endpoints are disabled")


@router.get("/debug/fingerprint")
async def debug_fingerprint():
    # Sequence input must never be placed in a URL query string.
    raise HTTPException(status_code=404, detail="Debug experiment endpoints are disabled")
