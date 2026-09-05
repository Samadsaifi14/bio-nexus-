from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.auth import get_user_id
from app.services.experiment import (
    archive_manifest,
    begin_experiment,
    build_fingerprint,
    compare_experiments,
    doi_export_metadata,
    finalize_experiment,
    get_experiment,
    get_experiment_by_id,
    persist_archive,
    search_experiments,
)
from app.services.provenance import trace_for_job, record_step

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class CloneExperimentRequest(BaseModel):
    new_job_id: str = Field(..., description="Job UUID that will own the cloned experiment version")
    sequence: str = Field(..., min_length=1, description="Original input sequence; checksum is verified against the source")
    parameters: dict | None = None


class DoiMetadataRequest(BaseModel):
    title: str | None = None
    creators: list[dict] | None = None


@router.get("")
async def list_experiments(
    limit: int = Query(20, ge=1, le=200),
    q: str | None = None,
    pipeline: str | None = None,
    status: str | None = None,
    user_id: str | None = Depends(get_user_id),
):
    """Searchable experiment registry for reproducibility and audit review."""
    try:
        return {"experiments": search_experiments(query=q, pipeline=pipeline, status=status, limit=limit)}
    except Exception as e:
        if "experiments" in str(e):
            logger.warning("Experiments list degraded (table missing or unreachable): %s", e)
            return {"experiments": [], "degraded": True}
        raise HTTPException(status_code=500, detail=f"Experiments list error: {type(e).__name__}: {e}")


@router.get("/id/{experiment_id}")
async def get_experiment_by_experiment_id(experiment_id: str, user_id: str | None = Depends(get_user_id)):
    exp = get_experiment_by_id(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"experiment": exp}


@router.get("/compare/{left_experiment_id}/{right_experiment_id}")
async def compare(
    left_experiment_id: str,
    right_experiment_id: str,
    user_id: str | None = Depends(get_user_id),
):
    left = get_experiment_by_id(left_experiment_id)
    right = get_experiment_by_id(right_experiment_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="One or both experiments were not found")
    return compare_experiments(left, right)


@router.get("/{job_id}")
async def get_experiment_by_job(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Immutable experiment record for a job, including its provenance DAG."""
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return {"experiment": exp}


@router.get("/{job_id}/provenance")
async def get_provenance(job_id: str, user_id: str | None = Depends(get_user_id)):
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return trace_for_job(job_id, exp["experiment_id"])


@router.get("/{job_id}/archive")
async def get_archive(job_id: str, persist: bool = False, user_id: str | None = Depends(get_user_id)):
    """Return a checksum-addressed experiment archive manifest.

    With ``persist=true`` the exact manifest is also stored with an archive
    timestamp, providing an auditable export event.
    """
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return persist_archive(job_id) if persist else archive_manifest(exp)


@router.post("/{job_id}/doi-metadata")
async def build_doi_metadata(
    job_id: str,
    request: DoiMetadataRequest,
    user_id: str | None = Depends(get_user_id),
):
    """Generate DOI-deposit-ready metadata without claiming a DOI was minted."""
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found for job")
    return doi_export_metadata(exp, title=request.title, creators=request.creators)


@router.post("/{job_id}/clone")
async def clone_experiment(
    job_id: str,
    request: CloneExperimentRequest,
    user_id: str | None = Depends(get_user_id),
):
    """Clone an experiment as a new version after verifying identical input."""
    source = get_experiment(job_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source experiment not found")
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
    finalize_experiment(job_id, status, error)
    return {"ok": True}


@router.post("/debug/new")
async def debug_new(job_id: str, sequence: str, pipeline: str = "debug"):
    exp_id = begin_experiment(job_id, sequence, pipeline)
    if not exp_id:
        raise HTTPException(status_code=500, detail="Experiment creation failed")
    return {"experiment_id": exp_id}


@router.post("/debug/trace")
async def debug_trace(job_id: str, node_id: str, tool: str, deps: list[str] | None = None):
    exp = get_experiment(job_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    record_step(exp["id"], node_id, tool=tool, deps=deps or [])
    return {"ok": True}


@router.get("/debug/fingerprint")
async def debug_fingerprint(sequence: str):
    return build_fingerprint(sequence)
