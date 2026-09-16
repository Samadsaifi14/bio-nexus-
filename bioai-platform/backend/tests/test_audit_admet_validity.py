"""Publication audit for ADMET/descriptors.

The deterministic descriptor layer is checked against RDKit's own documented
functions and a small external known-answer fixture (PubChem aspirin values).
Heuristic screening fields are also checked so BioNexus does not fabricate
quantities that require experimental potency or a validated QSAR model.
"""

from __future__ import annotations

import random

import pytest
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors

from app.tools.admet import compute_descriptors


ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
SEED = 20260916


def test_aspirin_known_answer_pubchem_2025_computed_properties():
    """Known-answer values from PubChem CID 2244.

    PubChem reports MW 180.16 g/mol, HBD 1, HBA 4 and TPSA 63.6 A^2.
    HBA is method-dependent; BioNexus explicitly uses RDKit's Lipinski-HBA
    convention for this field so the convention must be recorded in metadata.
    """
    result = compute_descriptors(ASPIRIN)
    assert result["formula"] == "C9H8O4"
    assert result["molecular_weight"] == pytest.approx(180.16, abs=0.01)
    assert result["tpsa"] == pytest.approx(63.6, abs=0.1)
    assert result["hbd"] == 1
    assert result["hba"] == 4
    assert result["heavy_atoms"] == 13
    conventions = result.get("_descriptor_conventions", {})
    assert conventions.get("hba") == "RDKit CalcNumLipinskiHBA"
    assert conventions.get("rotatable_bonds") == "RDKit Lipinski.NumRotatableBonds"


def _valid_random_smiles(n: int = 100):
    """Generate deterministic, sanitizable small molecules from simple motifs."""
    rng = random.Random(SEED)
    terminal = ["", "O", "N", "Cl", "Br", "C(=O)O", "C#N"]
    branch = ["", "(C)", "(O)"]
    yielded = 0
    while yielded < n:
        chain = "C" * rng.randint(1, 10)
        candidate = chain + rng.choice(branch) + rng.choice(terminal)
        mol = Chem.MolFromSmiles(candidate)
        if mol is None:
            continue
        yielded += 1
        yield Chem.MolToSmiles(mol)


def test_random_core_descriptors_equal_explicit_rdkit_conventions():
    for smiles in _valid_random_smiles():
        mol = Chem.MolFromSmiles(smiles)
        assert mol is not None
        observed = compute_descriptors(smiles)
        assert observed["formula"] == rdMolDescriptors.CalcMolFormula(mol)
        assert observed["molecular_weight"] == pytest.approx(round(Descriptors.MolWt(mol), 2), abs=1e-12)
        assert observed["logp"] == pytest.approx(round(Descriptors.MolLogP(mol), 2), abs=1e-12)
        assert observed["tpsa"] == pytest.approx(round(Descriptors.TPSA(mol, includeSandP=True), 2), abs=1e-12)
        assert observed["hbd"] == Lipinski.NumHDonors(mol)
        assert observed["hba"] == rdMolDescriptors.CalcNumLipinskiHBA(mol)
        assert observed["rotatable_bonds"] == Lipinski.NumRotatableBonds(mol)
        assert observed["heavy_atoms"] == mol.GetNumHeavyAtoms()
        assert observed["qed_score"] == pytest.approx(round(QED.qed(mol), 4), abs=1e-12)
        assert observed["molar_refractivity"] == pytest.approx(round(Crippen.MolMR(mol), 2), abs=1e-12)


def test_invalid_smiles_are_rejected_not_converted_to_results():
    rng = random.Random(SEED + 1)
    cases = ["not_a_smiles", "C1(CC", "[C", "(()", "@@@"]
    cases += ["".join(rng.choice("XYZ@#()") for _ in range(16)) for _ in range(15)]
    for candidate in cases:
        with pytest.raises(ValueError):
            compute_descriptors(candidate)


def test_lipophilic_efficiency_is_not_invented_without_potency():
    result = compute_descriptors(ASPIRIN)
    assert result["metabolism"]["lipophilic_efficiency"] is None
    note = result["metabolism"].get("lipophilic_efficiency_note", "").lower()
    assert "pic50" in note or "potency" in note


def test_unvalidated_ld50_numeric_estimate_is_withheld():
    result = compute_descriptors(ASPIRIN)
    assert result["toxicity"]["ld50_estimate_log"] is None
    assert result["toxicity"]["acute_toxicity_ld50"] == "Not predicted"
    assert "validated" in result["toxicity"].get("acute_toxicity_note", "").lower()


def test_rule_based_admet_is_explicitly_not_a_validated_qsar_prediction():
    result = compute_descriptors(ASPIRIN)
    methodology = result["_methodology"]
    for key in ("absorption_distribution_metabolism", "toxicity", "clearance"):
        item = methodology[key]
        text = f"{item.get('method', '')} {item.get('note', '')}".lower()
        assert "heuristic" in text or "not validated" in text
    assert "validated_qsar" not in str(methodology).lower()
