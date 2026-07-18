"""
Smoke tests for the ADMET descriptor endpoint.

Covers:
- Valid SMILES return 200 with correct shape
- Invalid SMILES return 422 or meaningful error
- Response contains 3a (core descriptors) and 3b (toxicity) sections
- _methodology metadata present
- Toxicity section contains _disclaimer
- All core numeric fields are finite numbers
"""

import math
import pytest
from tests.conftest import requires_rdkit

BASE = "/api/admet/descriptors"


@requires_rdkit
class TestADMETBasic:
    """Core endpoint health checks."""

    def test_aspirin_returns_200(self, client):
        resp = client.post(BASE, json={"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["result"] is not None

    def test_result_has_core_fields(self, client, valid_smiles):
        result = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]
        for field in [
            "smiles", "formula", "molecular_weight", "logp", "tpsa",
            "hbd", "hba", "rotatable_bonds", "qed_score",
            "heavy_atoms", "molar_refractivity", "molecular_volume",
            "fsp3", "ring_count", "aromatic_ring_count",
        ]:
            assert field in result, f"Missing core field: {field}"

    def test_numeric_fields_are_finite(self, client, valid_smiles):
        result = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]
        numeric_fields = [
            "molecular_weight", "logp", "tpsa", "qed_score",
            "molar_refractivity", "molecular_volume", "fsp3",
        ]
        for field in numeric_fields:
            val = result[field]
            assert isinstance(val, (int, float)), f"{field} is not numeric: {val}"
            assert math.isfinite(val), f"{field} is not finite: {val}"


@requires_rdkit
class TestADMETMethodology:
    """Verify 3a/3b split metadata."""

    def test_methodology_present(self, client, valid_smiles):
        result = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]
        assert "_methodology" in result

    def test_core_descriptors_are_3a(self, client, valid_smiles):
        meth = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["_methodology"]
        assert meth["core_descriptors"]["tier"] == "3a"
        assert meth["core_descriptors"]["confidence"] == "high"

    def test_toxicity_is_3b(self, client, valid_smiles):
        meth = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["_methodology"]
        assert meth["toxicity"]["tier"] == "3b"
        assert meth["toxicity"]["confidence"] == "approximate"

    def test_drug_likeness_is_3a(self, client, valid_smiles):
        meth = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["_methodology"]
        assert meth["drug_likeness"]["tier"] == "3a"


@requires_rdkit
class TestADMETToxicity:
    """Verify toxicity section shape and disclaimer."""

    def test_toxicity_has_disclaimer(self, client, valid_smiles):
        tox = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["toxicity"]
        assert "_disclaimer" in tox
        assert "heuristic" in tox["_disclaimer"].lower() or "no ML" in tox["_disclaimer"]

    def test_toxicity_has_all_fields(self, client, valid_smiles):
        tox = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["toxicity"]
        for field in [
            "ames_mutagenicity", "ames_alerts", "herg_liability",
            "hepatotoxicity_dili", "skin_sensitization",
            "acute_toxicity_ld50", "ld50_estimate_log", "risk_score",
        ]:
            assert field in tox, f"Missing toxicity field: {field}"

    def test_risk_score_in_range(self, client, valid_smiles):
        score = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["toxicity"]["risk_score"]
        assert 0 <= score <= 10


@requires_rdkit
class TestADMETSafety:
    """Verify drug-likeness and structural alerts sections."""

    def test_drug_likeness_has_lipinski(self, client, valid_smiles):
        dl = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["drug_likeness"]
        assert "lipinski" in dl
        assert "pass" in dl["lipinski"]
        assert "violation_count" in dl["lipinski"]

    def test_structural_alerts_present(self, client, valid_smiles):
        sa = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["structural_alerts"]
        assert "pains" in sa
        assert "brenk" in sa
        assert "total_alert_count" in sa

    def test_absorption_section_present(self, client, valid_smiles):
        abs_ = client.post(BASE, json={"smiles": valid_smiles}).json()["result"]["absorption"]
        assert "oral_bioavailability" in abs_
        assert "caco2_permeability" in abs_
        assert "hia" in abs_


@requires_rdkit
class TestADMETEdgeCases:
    """Edge cases and error handling."""

    def test_invalid_smiles_returns_error(self, client, invalid_smiles):
        resp = client.post(BASE, json={"smiles": invalid_smiles})
        assert resp.status_code in (400, 422, 500)
        body = resp.json()
        assert "error" in body or "detail" in body

    def test_empty_smiles_returns_422(self, client):
        resp = client.post(BASE, json={"smiles": ""})
        assert resp.status_code == 422

    def test_missing_smiles_returns_422(self, client):
        resp = client.post(BASE, json={})
        assert resp.status_code == 422

    def test_parametrized_molecules(self, client, sample_smiles):
        """Run every molecule in the parametrized fixture."""
        name, smiles = sample_smiles
        resp = client.post(BASE, json={"smiles": smiles})
        assert resp.status_code == 200, f"{name} failed: {resp.text}"
        result = resp.json()["result"]
        assert result is not None
        assert result["molecular_weight"] > 0
