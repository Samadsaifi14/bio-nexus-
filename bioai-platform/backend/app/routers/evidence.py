"""AI Evidence Engine routes (Component 9):

- GET /api/experiments/{job_id}/evidence        — the evidence graph for a job
                                                  (claims -> sources -> citations).
- GET /api/experiments/{job_id}/evidence/validate — validation report over the graph.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.engines.evidence_engine import evidence_engine
from app.services.auth import get_user_id
from app.services.benchmarks import _fetch_job_context
from app.services.evidence_graph import assemble_evidence

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evidence"])


@router.get("/api/experiments/{job_id}/evidence")
async def experiment_evidence(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Evidence graph linking every AI claim to its supporting computation."""
    context = _fetch_job_context(job_id)
    if not context:
        raise HTTPException(status_code=404, detail="Job context not found or empty")
    return assemble_evidence(context)


@router.get("/api/experiments/{job_id}/evidence/validate")
async def experiment_evidence_validate(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Validation report over the evidence graph (honesty invariant)."""
    context = _fetch_job_context(job_id)
    if not context:
        raise HTTPException(status_code=404, detail="Job context not found or empty")
    graph = assemble_evidence(context)
    result = evidence_engine.parse(graph)
    report = evidence_engine.validate(result)
    return report.to_dict()