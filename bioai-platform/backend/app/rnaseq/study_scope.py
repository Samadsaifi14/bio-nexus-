"""RNA-seq study-scope classification for manuscript-safe result handling."""

from __future__ import annotations

from typing import Any

FULL_SALS_GENES = 22085
FULL_SALS_SAMPLES = 18
CI_SALS_GENES = 221
CI_SOURCE_PREFIX = "bundled-deterministic-every-100th-gene-subset"


def classify_rnaseq_study_scope(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary") or {}
    provenance = result.get("provenance") or {}
    genes = int(summary.get("genes_input") or 0)
    samples = int(summary.get("samples") or 0)
    source = str(provenance.get("source_label") or "")
    reference = str(summary.get("reference_level") or provenance.get("reference_level") or "")
    test = str(summary.get("test_level") or provenance.get("test_level") or "")
    design = str(summary.get("design") or "")

    if source.startswith(CI_SOURCE_PREFIX):
        return {
            "classification": "CI_REGRESSION_ONLY",
            "full_study": False,
            "biological_claims_allowed": False,
            "manuscript_claim_ready": False,
            "reason": (
                "The bundled 221-gene every-100th-gene fixture exists to detect software regressions. "
                "It is not a biological-analysis substitute for the complete SALS matrix."
            ),
            "observed_shape": {"genes": genes, "samples": samples},
            "expected_full_study_shape": {"genes": FULL_SALS_GENES, "samples": FULL_SALS_SAMPLES},
        }

    looks_like_full_sals = (
        genes == FULL_SALS_GENES
        and samples == FULL_SALS_SAMPLES
        and reference.casefold() == "healthy"
        and test.casefold() == "sals"
    )
    if looks_like_full_sals:
        return {
            "classification": "FULL_SALS_STATISTICAL_EXECUTION",
            "full_study": True,
            "retained_derived_artifacts": True,
            "recorded_design": design or "condition/covariates recorded in run provenance",
            "biological_claims_allowed": False,
            "manuscript_claim_ready": False,
            "reason": (
                "The complete expected matrix shape was analyzed, but ALS-associated biological claims "
                "still require independently reviewable interpretation and study-design review."
            ),
            "observed_shape": {"genes": genes, "samples": samples},
            "requirements_before_biological_claim": [
                "verify the complete 22,085-gene matrix and all 18 samples by retained checksums",
                "review the experimental design and all relevant covariates/confounders",
                "review QC before interpreting differential-expression calls",
                "independent biological interpretation/review",
            ],
        }

    return {
        "classification": "USER_SUPPLIED_STATISTICAL_EXECUTION",
        "full_study": False,
        "biological_claims_allowed": False,
        "manuscript_claim_ready": False,
        "reason": "DESeq2 statistical output is authoritative for the recorded inputs; biological interpretation is a separate review step.",
        "observed_shape": {"genes": genes, "samples": samples},
    }
