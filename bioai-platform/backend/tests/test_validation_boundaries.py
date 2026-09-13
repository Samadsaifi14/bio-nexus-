import pytest

from app.benchmarking.ai_grounding import evaluate_grounding
from app.benchmarking.docking_redock import canonical_redocking_fixture
from app.benchmarking.giab import (
    GermlineBenchmarkPlanError,
    GermlineBenchmarkRequest,
    build_germline_truth_benchmark_plan,
)
from app.benchmarking.validation_claims import validation_claims
from app.rnaseq.study_scope import classify_rnaseq_study_scope


def _giab_request(**overrides):
    data = {
        "query_vcf": "/work/query.vcf.gz",
        "truth_vcf": "/truth/HG002.vcf.gz",
        "confident_regions_bed": "/truth/HG002.confident.bed.gz",
        "reference_fasta": "/refs/GRCh38.fa",
        "query_reference_build": "GRCh38",
        "truth_reference_build": "GRCh38",
        "truth_set_id": "GIAB-HG002-pinned-release",
        "output_prefix": "/results/hg002",
        "stratification_tsv": "/truth/GRCh38-stratifications.tsv",
    }
    data.update(overrides)
    return GermlineBenchmarkRequest(**data)


def test_giab_plan_requires_matched_reference_builds_and_confident_regions():
    plan = build_germline_truth_benchmark_plan(_giab_request())
    assert plan["execution_status"] == "PLANNED_NOT_EXECUTED"
    assert plan["accuracy_claim_allowed"] is False
    assert plan["command_argv"][:3] == ["hap.py", "/truth/HG002.vcf.gz", "/work/query.vcf.gz"]
    assert "-f" in plan["command_argv"]
    assert "--stratification" in plan["command_argv"]
    assert plan["shell_interpolation_allowed"] is False


def test_giab_plan_rejects_reference_build_mismatch():
    with pytest.raises(GermlineBenchmarkPlanError, match="Reference-build mismatch"):
        build_germline_truth_benchmark_plan(_giab_request(truth_reference_build="GRCh37"))


def test_giab_plan_rejects_synthetic_truth_as_production_accuracy_evidence():
    with pytest.raises(GermlineBenchmarkPlanError, match="non-synthetic"):
        build_germline_truth_benchmark_plan(_giab_request(truth_set_id="synthetic-WGS-control"))


def test_bbs1_claim_contract_never_implies_complete_input_space():
    claims = validation_claims()
    assert claims["bbs1"]["complete_input_space_covered"] is False
    assert claims["bbs1"]["platform_wide_accuracy_claim_allowed"] is False
    assert claims["deployment"]["control_plane_liveness_implies_end_to_end_workflow_availability"] is False


def test_ai_grounding_pass_is_not_scientific_truth_validation():
    result = evaluate_grounding({
        "generated_text": "Observed value was 42.0.",
        "evidence_text": "Observed value was 42.0.",
        "generated_citations": ["PMID:1"],
        "allowed_citations": ["PMID:1"],
        "claims": [{"id": "c1", "evidence_class": "AI-generated interpretation", "evidence_refs": ["result:1"]}],
    })
    assert result["grounding_passed"] is True
    assert result["scientifically_validated"] is False
    assert result["biological_truth_established"] is False


def test_sals_ci_fixture_is_never_promoted_to_biological_study():
    scope = classify_rnaseq_study_scope({
        "summary": {"genes_input": 221, "samples": 18, "reference_level": "healthy", "test_level": "SALS"},
        "provenance": {"source_label": "bundled-deterministic-every-100th-gene-subset-of-course-supplied-cerebellum-SALS-matrix"},
    })
    assert scope["classification"] == "CI_REGRESSION_ONLY"
    assert scope["biological_claims_allowed"] is False
    assert scope["manuscript_claim_ready"] is False


def test_full_sals_shape_is_statistical_execution_not_automatic_biological_truth():
    scope = classify_rnaseq_study_scope({
        "summary": {
            "genes_input": 22085,
            "samples": 18,
            "reference_level": "healthy",
            "test_level": "SALS",
            "design": "~ condition",
        },
        "provenance": {"source_label": "user-upload"},
    })
    assert scope["classification"] == "FULL_SALS_STATISTICAL_EXECUTION"
    assert scope["full_study"] is True
    assert scope["retained_derived_artifacts"] is True
    assert scope["manuscript_claim_ready"] is False


def test_redocking_fixture_no_longer_depends_on_failed_1iep_sdf_path():
    fixture = canonical_redocking_fixture()
    assert fixture["fixture_id"] == "BBS1-DOCK-1STP-BTN"
    assert fixture["pdb_id"] == "1STP"
    assert fixture["sdf_dependency"] is False
    assert fixture["pose_rmsd_threshold_angstrom"] == 2.0
    assert fixture["accuracy_claim_allowed"] is False
    assert fixture["retired_blocked_fixture"]["pdb_id"] == "1IEP"
