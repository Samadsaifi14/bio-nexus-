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
        "retained_real_data_benchmark": {
            "dataset": "GSE67196",
            "unique_gene_ids_input": 23344,
            "samples": 18,
            "design": "~condition",
            "experimental_unit_status": "NOT_DECLARED",
            "workflow_artifact_sha256": "ce0fa52c75e0b5c40d7e5cc8c7d222fc03416d57f0a1ecf1db4405d9575a9cf0",
            "supports_reproducible_execution_claim": True,
            "supports_als_biomarker_or_clinical_claim": False,
        },
        "full_study_requirements": [
            "official public-source count matrix with source checksum",
            "all declared samples and exact source mapping",
            "predeclared statistical design and thresholds",
            "retained deterministic outputs, figures and provenance",
            "experimental-unit/covariate review before biological interpretation",
        ],
        "automatic_als_biological_claims_allowed": False,
    },
    "docking": {
        "canonical_redocking_fixture": "BBS1-DOCK-1STP-BTN",
        "retired_blocked_fixture": "1IEP ligand-SDF path",
        "canonical_fixture_status": "PASSED_RETAINED_SINGLE_FIXTURE",
        "retained_rmsd_angstrom": 0.7252,
        "predeclared_threshold_angstrom": 2.0,
        "retained_workflow_run_id": 35389973834,
        "retained_artifact_sha256": "7844d5f217a2c7105ca4c022a2b18667e2fc085dd10df2ee8fcb1db26fbacba2",
        "pose_recovery_claim_scope": "1STP-biotin fixture under the recorded preparation and Vina protocol only",
        "general_docking_accuracy_claim_allowed": False,
        "affinity_validation_claim_allowed": False,
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
