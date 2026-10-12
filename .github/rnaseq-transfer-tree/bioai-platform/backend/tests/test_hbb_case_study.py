from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_case_module():
    path = Path(__file__).resolve().parents[1] / "benchmark" / "case-studies" / "hbb-variant-mapping" / "run.py"
    spec = importlib.util.spec_from_file_location("hbb_variant_case", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hbb_e7v_case_is_deterministic_and_mapped():
    case = _load_case_module()
    result = case.run_case()

    assert result["status"] == "executed"
    assert result["source"]["accession"] == "P68871"
    assert result["source"]["sequence_length"] == 147
    assert result["source"]["sequence_sha256"] == case.EXPECTED_WT_SHA256
    assert result["variant"]["position"] == 7
    assert result["variant"]["ref"] == "E"
    assert result["variant"]["alt"] == "V"
    assert result["variant"]["mutant_sequence_sha256"] == case.EXPECTED_MUTANT_SHA256
    assert result["deterministic_result"]["alignment_position"] == 7
    assert result["deterministic_result"]["reference_symbol"] == "E"
    assert result["deterministic_result"]["sequence_count"] == 2
    assert result["deterministic_result"]["alignment_length"] == 147
    assert result["reproducibility"]["random_seed_required"] is False
    assert "does not establish diagnostic validity" in result["scientific_boundary"]


def test_hbb_fixture_rejects_reference_drift():
    case = _load_case_module()
    assert case.sha256_text(case.HBB_WILDTYPE) == case.EXPECTED_WT_SHA256
    mutant = case.build_mutant()
    assert mutant[6] == "V"
    assert case.sha256_text(mutant) == case.EXPECTED_MUTANT_SHA256
