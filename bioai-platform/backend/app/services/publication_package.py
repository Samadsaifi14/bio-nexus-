"""Assemble the paper-facing BioNexus contribution into one auditable package."""
from __future__ import annotations

from typing import Any

from app.services.evidence_graph import assemble_evidence
from app.services.publication import render_paper
from app.services.supplementary_material import build_supplementary_manifest, manuscript_checklist
from app.services.reproducibility_bundle import build_bundle


def build_publication_package(
    *,
    job_id: str,
    context: dict[str, Any],
    supplementary_assets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = assemble_evidence(context)
    paper = render_paper(context, job_id=job_id)
    supplementary = build_supplementary_manifest(supplementary_assets)
    reproducibility = build_bundle(job_id)
    evidence_summary = evidence.get("summary") or {}

    contribution = {
        "primary": "BioNexus improves bioinformatics reproducibility and interpretability by coupling each persisted scientific claim to an auditable provenance chain and reproducibility contract.",
        "mechanism": "claim -> evidence -> algorithm -> database -> version -> parameters -> confidence -> benchmark",
        "evaluation_requirements": [
            "external benchmark datasets",
            "cross-platform execution",
            "confidence intervals and effect sizes for performance comparisons",
            "visible failure analysis",
            "independent reproduction from exported bundle"
        ],
        "prohibited_overclaim": "Do not state that BioNexus is more accurate, clinically validated, or superior to another platform unless the corresponding external comparison has been executed and persisted."
    }

    readiness = {
        "evidence_graph_present": bool(evidence.get("nodes")),
        "unsupported_claim_rate": evidence_summary.get("unsupported_claim_rate"),
        "all_claims_admitted": evidence_summary.get("rejected_claim_count") == 0,
        "supplementary_complete": supplementary.get("complete", False),
        "reproducibility_bundle_available": reproducibility is not None,
        "reproducibility_ledger_valid": bool((reproducibility or {}).get("ledger_validation", {}).get("valid")),
    }
    readiness["paper_package_complete"] = all([
        readiness["evidence_graph_present"],
        readiness["all_claims_admitted"],
        readiness["supplementary_complete"],
        readiness["reproducibility_bundle_available"],
        readiness["reproducibility_ledger_valid"],
    ])

    return {
        "schema": "bionexus-publication-package/v1",
        "experiment_id": job_id,
        "scientific_contribution": contribution,
        "readiness": readiness,
        "paper": paper,
        "evidence_graph": evidence,
        "supplementary_material": supplementary,
        "supplementary_checklist": manuscript_checklist(supplementary),
        "reproducibility_bundle": reproducibility,
        "boundary": "A complete package is a reproducibility/publication artifact. Journal acceptance and scientific validity still depend on external evidence, appropriate study design and peer review."
    }
