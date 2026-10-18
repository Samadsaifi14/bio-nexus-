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


def _native_atoms(mol, shift=0, serial_offset=0):
    types = {'C': 'C', 'N': 'N', 'O': 'OA', 'S': 'SA'}
    lines = []
    for index, atom in enumerate(mol.GetAtoms()):
        point = mol.GetConformer().GetAtomPosition(index)
        lines.append(f'ATOM  {index + 1 + serial_offset:5d}  C   UNL     1    '
                     f'{point.x + shift:8.3f}{point.y:8.3f}{point.z:8.3f}  0.00  0.00     0.000 {types[atom.GetSymbol()]}')
    return '\n'.join(lines) + '\n'


def test_native_serial_mapping_preserves_translated_pose_without_alignment():
    reference = Chem.AddHs(Chem.MolFromSmiles('CCO'))
    AllChem.EmbedMolecule(reference, randomSeed=7)
    reference = Chem.RemoveHs(reference)
    prepared = _native_atoms(reference)
    pose = _native_atoms(reference, shift=10)
    restored = runner._native_pose_molecule(pose, prepared, reference)
    from app.benchmarking.docking_redock import symmetry_aware_pose_rmsd
    assert symmetry_aware_pose_rmsd(reference, restored) == pytest.approx(10, abs=0.001)
    assert Chem.MolToSmiles(restored) == Chem.MolToSmiles(reference)


@pytest.mark.parametrize('corruption', ['missing', 'duplicate', 'element', 'serial', 'nonfinite'])
def test_native_serial_mapping_rejects_corrupt_pose(corruption):
    reference = Chem.AddHs(Chem.MolFromSmiles('CCO'))
    AllChem.EmbedMolecule(reference, randomSeed=7)
    reference = Chem.RemoveHs(reference)
    prepared = _native_atoms(reference)
    lines = prepared.splitlines()
    if corruption == 'missing': lines.pop()
    elif corruption == 'duplicate': lines.append(lines[0])
    elif corruption == 'element': lines[0] = lines[0][:-1] + 'N'
    elif corruption == 'serial': lines[0] = lines[0][:6] + '   99' + lines[0][11:]
    else: lines[0] = lines[0][:30] + '     nan' + lines[0][38:]
    with pytest.raises(ValueError):
        runner._native_pose_molecule('\n'.join(lines), prepared, reference)
