"""Tests for the ScientificResult contract and validation registry."""

import pytest

from app.scientific.contract import (
    ScientificResult,
    ScientificStatus,
    build_result,
    canonical_json,
    sha256_hex,
)
from app.scientific.registry import (
    RegistryError,
    ValidationState,
    module_validation_state,
    require_validation_evidence,
    registry_state,
    transition,
)


class TestScientificResultContract:
    def test_status_enum_values(self):
        assert [s.value for s in ScientificStatus] == [
            "VALID",
            "DEGRADED",
            "NOT_EVALUATED",
            "FAILED",
        ]

    def test_build_result_populates_output_hash(self):
        r = build_result(
            status=ScientificStatus.VALID,
            method="minimap2-variants-consensus",
            engine="minimap2",
            database="none",
            results={"consensus": "ACGT"},
        )
        assert r.output_sha256 == sha256_hex(canonical_json(r.to_dict(output_sha256="")))
        assert r.status == ScientificStatus.VALID

    def test_input_hash_from_data_preferred(self):
        r1 = build_result(
            status=ScientificStatus.VALID,
            method="m",
            engine="e",
            input_data=b"ACGT",
        )
        r2 = build_result(
            status=ScientificStatus.VALID,
            method="m",
            engine="e",
            input_sha256=sha256_hex("ACGT"),
        )
        assert r1.input_sha256 == sha256_hex(b"ACGT")
        assert r1.input_sha256 == r2.input_sha256

    def test_input_hash_from_parameters_when_no_input(self):
        r = build_result(status=ScientificStatus.VALID, method="m", engine="e", parameters={"x": 1})
        assert r.input_sha256 == sha256_hex(canonical_json({"x": 1}))

    def test_fallback_method_only_when_fallback_used(self):
        r = build_result(
            status=ScientificStatus.DEGRADED,
            method="exploratory SASA heuristic",
            engine="biopython",
            fallback_used=True,
            fallback_method="fpocket unavailable",
        )
        assert r.fallback_used is True
        assert r.fallback_method == "fpocket unavailable"

        clean = build_result(status=ScientificStatus.VALID, method="m", engine="e")
        assert clean.fallback_used is False
        assert clean.fallback_method is None

    def test_failed_status_allows_no_results_fabrication(self):
        r = build_result(
            status=ScientificStatus.FAILED,
            method="CASTp",
            engine="castp",
            results={"error": "CASTp service unreachable"},
        )
        assert r.status.value == "FAILED"
        assert r.results["error"]

    def test_round_trip_to_dict(self):
        r = build_result(
            status=ScientificStatus.DEGRADED,
            method="msa",
            engine="mafft",
            engine_version="7.525",
            fallback_used=True,
            fallback_method="clustal omega unavailable",
            results={"aln_len": 100},
            plots=[{"kind": "depth", "data": [1, 2]}],
        )
        obj = r.to_dict()
        assert obj["engine_version"] == "7.525"
        restored = ScientificResult.from_dict(obj)
        assert restored == r

    def test_from_dict_restores_payload(self):
        r = build_result(
            status=ScientificStatus.VALID,
            method="blast",
            engine="blastp",
            results={"hits": ["sp|P04637"]},
        )
        clone = ScientificResult.from_dict(r.to_dict())
        assert clone.results["hits"] == ["sp|P04637"]
        assert clone.method == "blast"


class TestValidationRegistry:
    def test_initial_registry_states(self):
        reg = registry_state()
        assert reg["sequence_utilities"]["state"] == "VALIDATED"
        assert reg["pairwise_alignment"]["state"] == "VALIDATED"
        assert reg["castp"]["state"] == "NOT_EVALUATED"
        assert reg["ngs_wgs_accuracy"]["state"] == "NOT_EVALUATED"
        assert reg["md"]["state"] == "METHOD_VERIFIED"
        assert reg["blast"]["state"] == "VALIDATION_PENDING"

    def test_registry_isolation_between_tests(self):
        _ = registry_state()

    def test_downgrade_allowed_without_evidence(self):
        row = transition("castp", ValidationState.VALIDATION_PENDING, reason="campaign planned")
        assert row["state"] == "VALIDATION_PENDING"

    def test_manual_upgrade_requires_evidence(self):
        transition("ngs_wgs_accuracy", ValidationState.VALIDATION_PENDING, reason="campaign planned")
        with pytest.raises(RegistryError):
            transition(
                "ngs_wgs_accuracy",
                ValidationState.VALIDATED,
                reason="no evidence behind this",
            )

    def test_promotion_with_retained_benchmark_evidence(self):
        evidence = require_validation_evidence(
            run_id="bench-2026-abc",
            artifacts=["truth.vcf", "conf.bed", "hap.py.summary.csv"],
            metrics={"precision": 0.99, "recall": 0.98, "f1": 0.985},
        )
        row = transition(
            "ngs_wgs_accuracy",
            ValidationState.VALIDATED,
            evidence=evidence,
            reason="GIAB HG002 chr20 hap.py benchmark retained",
        )
        assert row["state"] == "VALIDATED"
        assert row["evidence"]["run_id"] == "bench-2026-abc"
        assert row["evidence"]["evidence_sha256"]

    def test_unknown_module_returns_not_evaluated(self):
        assert module_validation_state("does-not-exist") == ValidationState.NOT_EVALUATED


@pytest.fixture(autouse=True)
def _reset_registry():
    from app.scientific import registry

    registry._REGISTRY = None
    yield
    registry._REGISTRY = None