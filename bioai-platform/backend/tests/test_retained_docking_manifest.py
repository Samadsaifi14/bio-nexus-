"""Integrity checks for the retained canonical 1STP redocking evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "benchmark" / "real_data" / "DOCKING_1STP" / "retained_run_manifest.json"


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_retained_1stp_redocking_passes_predeclared_threshold():
    m = _load()
    protocol = m["predeclared_protocol"]
    result = m["result"]
    assert m["benchmark_id"] == "BBS1-DOCK-1STP-BTN"
    assert protocol["seed"] == 42
    assert protocol["exhaustiveness"] == 32
    assert protocol["num_modes"] == 20
    assert protocol["acceptance_threshold_angstrom"] == 2.0
    assert result["status"] == "PASSED"
    assert result["passed"] is True
    assert result["rmsd_angstrom"] == 0.7252
    assert result["rmsd_angstrom"] <= protocol["acceptance_threshold_angstrom"]
    assert result["heavy_atom_count"] == 16


def test_retained_1stp_redocking_locks_execution_and_hashes():
    m = _load()
    run = m["retained_execution"]
    assert run["workflow_run_id"] == 35389973834
    assert run["workflow_head_sha"] == "af008e43e61b32760ff618e43395940656d1543f"
    assert run["artifact_id"] == 10565356302
    assert run["artifact_zip_sha256"] == "7844d5f217a2c7105ca4c022a2b18667e2fc085dd10df2ee8fcb1db26fbacba2"
    assert run["archival_status"] == "WORKFLOW_ARTIFACT_NOT_PERSISTENT_ARCHIVE"
    for digest in m["evidence_sha256"].values():
        assert len(digest) == 64
        int(digest, 16)


def test_retained_1stp_redocking_claim_is_fixture_scoped():
    boundary = _load()["claim_boundary"].lower()
    for phrase in ("single predeclared", "does not validate affinity", "other receptors or ligands", "clinical", "superiority"):
        assert phrase in boundary
