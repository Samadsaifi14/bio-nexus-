"""Validation-registry path and promotion-policy regression checks."""

from pathlib import Path

from app.science import validation_registry as registry


def test_validation_registry_points_to_repository_benchmark_directory():
    repo_root = Path(__file__).resolve().parents[3]
    assert registry.REPOSITORY_ROOT == repo_root
    assert registry.EVIDENCE_DIR == repo_root / "benchmark" / "validation-registry"


def test_registry_does_not_promote_without_integrity_checked_artifact():
    payload = registry.get_validation_registry()
    assert payload["policy"]["manual_validation_promotion"] is False
    assert payload["policy"]["validated_requires_benchmark_artifact"] is True
    for module, record in payload["modules"].items():
        if record["status"] == "VALIDATED":
            assert record["benchmark_evidence"] is not None, module
            assert record.get("evidence_sha256"), module


def test_scoped_method_verification_does_not_equal_platform_accuracy():
    payload = registry.get_validation_registry()["modules"]
    assert payload["docking"]["status"] == "METHOD_VERIFIED"
    assert "single-fixture" in payload["docking"]["scope"]
    assert payload["ngs_wgs_accuracy"]["status"] == "NOT_EVALUATED"
