"""AI Evidence Engine routes.

Reviewer-facing contracts:
- GET /api/experiments/{job_id}/evidence
- GET /api/experiments/{job_id}/evidence/claims/{claim_id}
- GET /api/experiments/{job_id}/evidence/validate

The claim route returns the exact typed subgraph a UI can open when a reviewer
clicks an AI sentence.
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


def _claim_subgraph(graph: dict, claim_id: str) -> dict:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    node_by_id = {node.get("id"): node for node in nodes}
    claim = node_by_id.get(claim_id)
    if not claim or claim.get("type") != "claim":
        raise HTTPException(status_code=404, detail="Evidence claim not found")

    # Traverse outward from the clicked claim. The graph is acyclic by contract.
    selected = {claim_id}
    frontier = [claim_id]
    while frontier:
        current = frontier.pop(0)
        for edge in edges:
            if edge.get("from") == current and edge.get("to") not in selected:
                selected.add(edge["to"])
                frontier.append(edge["to"])

    selected_nodes = [node_by_id[nid] for nid in selected if nid in node_by_id]
    selected_edges = [e for e in edges if e.get("from") in selected and e.get("to") in selected]
    by_type: dict[str, list[dict]] = {}
    for node in selected_nodes:
        by_type.setdefault(str(node.get("type")), []).append(node)
    return {
        "schema": "bionexus-evidence-claim-trace/v1",
        "claim_id": claim_id,
        "claim": claim,
        "reviewer_path": graph.get("reviewer_path"),
        "nodes": selected_nodes,
        "edges": selected_edges,
        "by_type": by_type,
        "complete_path": all(by_type.get(t) for t in (graph.get("reviewer_path") or [])),
        "interpretation": "complete_path means every provenance node type is represented; it does not imply that the benchmark passed or that the biological claim is clinically validated.",
    }


@router.get("/api/experiments/{job_id}/evidence/claims/{claim_id}")
async def experiment_claim_evidence(job_id: str, claim_id: str, user_id: str | None = Depends(get_user_id)):
    """Return the reviewer-clickable provenance chain for one AI claim."""
    context = _fetch_job_context(job_id)
    if not context:
        raise HTTPException(status_code=404, detail="Job context not found or empty")
    return _claim_subgraph(assemble_evidence(context), claim_id)


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
