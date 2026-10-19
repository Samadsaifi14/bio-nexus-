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


def test_site_failure_retains_native_pose_evidence_and_stays_failed(monkeypatch, tmp_path):
    """Replay retained native output to isolate failure control flow."""
    import json
    from types import SimpleNamespace
    from app.tools import docking

    artifacts = runner.REPO / 'benchmark/results/docking/redock/artifacts/20261012T080418163266Z/1STP'
    panel = json.loads((runner.FIXTURE_DIR / 'redock_panel.json').read_text())
    panel['complexes'] = [case for case in panel['complexes'] if case['id'] == '1STP']
    panel_path = tmp_path / 'panel.json'
    panel_path.write_text(json.dumps(panel))
    output = tmp_path / 'output'
    monkeypatch.setattr(runner.sys, 'argv', ['runner', '--panel', str(panel_path), '--outdir', str(output)])
    monkeypatch.setattr(runner, '_tools_available', lambda: (True, []))
    monkeypatch.setattr(runner, '_vina_bin', lambda: __file__)
    monkeypatch.setattr(runner.shutil, 'which', lambda _: __file__)
    source = (artifacts / 'source.pdb').read_text()
    monkeypatch.setattr(runner, '_fetch_pdb', lambda _: source)
    _, ligand = runner._split_ligand_receptor(source, 'BTN')
    center = runner._heavy_centroid(ligand)
    monkeypatch.setattr(docking, 'compute_pocket_grid', lambda _: {
        'center': [center[0] + 9, center[1], center[2]], 'size': [20, 20, 20]})
    monkeypatch.setattr(docking, 'pdb_to_pdbqt_receptor', lambda _: (artifacts / 'receptor.pdbqt').read_text())
    executions = []

    def native_replay(*args, **kwargs):
        executions.append(True)
        native = (artifacts / 'vina_output.pdbqt').read_text()
        return {'result_pdbqt': native, 'num_poses': len(runner._extract_pdbqt_models(native)),
                'vina_log': (artifacts / 'vina.log').read_text(), 'vina_version': 'fixture replay'}

    def conversion(command, **kwargs):
        if '-O' in command:
            destination = Path(command[command.index('-O') + 1])
            source_name = {'lig_ref.sdf': 'lig_ref.sdf', 'lig.pdbqt': 'lig.pdbqt',
                           'top_pose.sdf': 'top_pose.sdf'}[destination.name]
            destination.write_bytes((artifacts / source_name).read_bytes())
        return SimpleNamespace(returncode=0, stdout='retained fixture replay', stderr='')

    monkeypatch.setattr(docking, 'run_vina', native_replay)
    monkeypatch.setattr(runner.subprocess, 'run', conversion)
    assert runner.main() == 1
    case = json.loads((output / 'latest.json').read_text())['results'][0]
    assert executions == [True]
    assert case['site_coverage_passed'] is False
    assert case['pose_recovery_passed'] is True
    assert case['passed'] is False
    assert case['top_pose_rmsd_angstrom'] < 2
    assert {'vina_output.pdbqt', 'top_pose_chemical_graph.sdf', 'vina.log'} <= case['artifact_sha256'].keys()


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
