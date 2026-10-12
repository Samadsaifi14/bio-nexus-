"""Benchmark preparation regressions independent of live docking binaries."""
import importlib.util
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

runner_path = Path(__file__).resolve().parents[3] / "benchmark/fixtures/docking/run_redock_panel.py"
spec = importlib.util.spec_from_file_location("redock_runner", runner_path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_chemistry_reconstruction_does_not_move_a_translated_pose():
    reference = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    assert AllChem.EmbedMolecule(reference, randomSeed=7) == 0
    pose = Chem.RemoveHs(reference)
    conf = pose.GetConformer()
    for i, atom in enumerate(pose.GetAtoms()):
        point = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (point.x + 10, point.y, point.z))
        atom.SetNumExplicitHs(0)
        atom.SetNoImplicit(True)
    Chem.SanitizeMol(pose)
    block = Chem.MolToMolBlock(pose)
    restored = runner._restore_pose_chemistry(block, reference)
    assert restored.GetConformer().GetPositions() == pytest.approx(conf.GetPositions(), abs=1e-4)
    assert runner._rmsd_vs_crystal(block, reference) == pytest.approx(10, abs=1e-4)


def test_pdbqt_models_keep_pose_numbers_and_coordinates():
    text = "MODEL 1\nATOM coordinates1\nENDMDL\nMODEL 2\nATOM coordinates2\nENDMDL\n"
    assert runner._extract_pdbqt_models(text) == {1: "ATOM coordinates1\n", 2: "ATOM coordinates2\n"}


def test_crystal_extraction_selects_one_ligand_residue():
    line = "HETATM  903  C11 BTN A 300       9.051   4.576 -14.459  1.00 21.57           C  "
    second = line[:22] + " 301" + line[26:]
    _, ligand = runner._split_ligand_receptor(line + "\n" + second, "BTN")
    assert ligand == [line]
