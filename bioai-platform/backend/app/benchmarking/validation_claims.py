"""Machine-readable scientific validation boundaries for BioNexus.

This module deliberately separates software execution from scientific validation.
A listed capability is never promoted to a stronger claim without retained evidence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_VALIDATION_CLAIMS: dict[str, dict[str, Any]] = {
    "bbs1": {
        "evidence_scope": "module-specific reference concordance and deterministic fixtures",
        "complete_input_space_covered": False,
        "platform_wide_accuracy_claim_allowed": False,
        "claim_ceiling": "module-specific validation only",
        "required_for_expansion": [
            "predeclared representative input strata",
            "retained execution artifacts",
            "reference implementation outputs",
            "failure-state coverage",
            "regression evidence across supported input classes",
        ],
    },
    "germline_ngs": {
        "synthetic_control_scope": "functional and portability regression only",
        "synthetic_control_establishes_production_accuracy": False,
        "formal_benchmark_status": "NOT_EVALUATED",
        "formal_benchmark_requires": [
            "non-synthetic accepted truth set",
            "matching query and truth reference builds",
            "truth VCF",
            "confident-region BED",
            "haplotype-aware evaluator",
            "SNP and INDEL TP/FP/FN, precision, recall and F1",
            "genotype concordance and no-call counts",
            "stratified difficult-region metrics",
            "input/resource/evaluator checksums and provenance",
        ],
        "accuracy_claim_allowed_before_completed_report": False,
    },
    "rnaseq_sals": {
        "ci_fixture": {
            "genes": 221,
            "samples": 18,
            "scope": "CI_REGRESSION_ONLY",
            "supports_biological_claims": False,
        },
        "full_study_expected_shape": {"genes": 22085, "samples": 18},
        "full_study_requirements": [
            "complete 22,085-gene matrix",
            "all 18 samples",
            "fully recorded statistical design and covariates",
            "retained deterministic outputs and provenance",
            "independently reviewable biological interpretation",
        ],
        "automatic_als_biological_claims_allowed": False,
    },
    "docking": {
        "canonical_redocking_fixture": "BBS1-DOCK-1STP-BTN",
        "retired_blocked_fixture": "1IEP ligand-SDF path",
        "canonical_fixture_status": "FIXTURE_READY_EXECUTION_EVIDENCE_REQUIRED",
        "pose_accuracy_claim_allowed_without_retained_rmsd_artifact": False,
    },
    "md": {
        "hosted_engine": "OpenMM",
        "solvent_scope": "implicit solvent only",
        "explicit_solvent_production_equivalence": False,
        "claim_ceiling": "hosted implicit-solvent MD within recorded force-field/solvent configuration",
    },
    "ai": {
        "grounding_checks_establish": "correspondence between generated text and recorded evidence",
        "grounding_checks_establish_biological_truth": False,
        "grounding_checks_equal_independent_scientific_validation": False,
    },
    "deployment": {
        "components": [
            "web_control_plane",
            "production_compute_worker",
            "scientific_artifact_store",
        ],
        "component_availability_is_independent": True,
        "control_plane_liveness_implies_end_to_end_workflow_availability": False,
    },
}


def validation_claims() -> dict[str, dict[str, Any]]:
    """Return a defensive copy so API consumers cannot mutate the registry."""
    return deepcopy(_VALIDATION_CLAIMS)
