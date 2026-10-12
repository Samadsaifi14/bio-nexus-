"""Reference tests for the BBS-1 redocking RMSD metric."""

import pytest

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem
from rdkit.Chem import AllChem

from app.benchmarking.docking_redock import evaluate_redocking


def _embedded_ethanol(seed: int = 7):
    mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    assert AllChem.EmbedMolecule(mol, randomSeed=seed) == 0
    return mol


def test_identical_pose_has_zero_rmsd():
    ref = _embedded_ethanol()
    pred = Chem.Mol(ref)
    result = evaluate_redocking(ref, pred)
    assert result.rmsd_angstrom == pytest.approx(0.0, abs=1e-4)
    assert result.passed is True
    assert result.threshold_angstrom == 2.0
    assert "symmetry-aware" in result.metric


def test_atom_count_mismatch_is_rejected():
    ref = _embedded_ethanol()
    pred = Chem.AddHs(Chem.MolFromSmiles("CC"))
    assert AllChem.EmbedMolecule(pred, randomSeed=9) == 0
    with pytest.raises(ValueError, match="heavy-atom counts differ"):
        evaluate_redocking(ref, pred)


def test_invalid_threshold_is_rejected():
    ref = _embedded_ethanol()
    with pytest.raises(ValueError, match="must be > 0"):
        evaluate_redocking(ref, Chem.Mol(ref), threshold_angstrom=0)


def test_translated_pose_fails_without_ligand_alignment():
    ref = _embedded_ethanol()
    pred = Chem.Mol(ref)
    conf = pred.GetConformer()
    for i in range(pred.GetNumAtoms()):
        point = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (point.x + 10, point.y, point.z))
    before = [tuple(conf.GetAtomPosition(i)) for i in range(pred.GetNumAtoms())]
    result = evaluate_redocking(ref, pred)
    assert result.rmsd_angstrom == pytest.approx(10.0, abs=1e-4)
    assert not result.passed
    assert [tuple(conf.GetAtomPosition(i)) for i in range(pred.GetNumAtoms())] == before


def test_atom_renumbering_retains_zero_rmsd():
    ref = _embedded_ethanol()
    pred = Chem.RenumberAtoms(ref, list(reversed(range(ref.GetNumAtoms()))))
    assert evaluate_redocking(ref, pred).rmsd_angstrom == pytest.approx(0, abs=1e-4)


@pytest.mark.parametrize("threshold", [float("nan"), float("inf")])
def test_nonfinite_threshold_is_rejected(threshold):
    ref = _embedded_ethanol()
    with pytest.raises(ValueError, match="finite"):
        evaluate_redocking(ref, Chem.Mol(ref), threshold)
