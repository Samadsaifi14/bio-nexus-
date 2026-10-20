"""Regression tests for the prospective multisite redocking method."""
import importlib.util
import sys
from pathlib import Path

import pytest

RUNNER_DIR = Path(__file__).resolve().parents[3] / "benchmark/fixtures/docking"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))
import run_multisite_panel as multisite


def _hetatm(serial, atom, resname, chain, residue, element, x=1.0):
    return (f"HETATM{serial:5d} {atom:<4s} {resname:>3s} {chain}{residue:4d}    "
            f"{x:8.3f}{2.0:8.3f}{3.0:8.3f}{1.0:6.2f}{20.0:6.2f}          {element:>2s}  ")


def test_multisite_splits_all_ligand_copies_and_explicit_receptor_chains():
    protein_a = "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 20.00           C  "
    protein_b = "ATOM      2  CA  ALA B   1       4.000   5.000   6.000  1.00 20.00           C  "
    source = "\n".join([protein_a, protein_b,
        _hetatm(3, "C1", "HTM", "A", 1001, "C"),
        _hetatm(4, "C1", "HTM", "B", 1001, "C"), "END"])
    receptor, copies = multisite._split_all_copies(source, "HTM", {"A"})
    assert "ALA A" in receptor
    assert "ALA B" not in receptor
    assert len(copies) == 2
    assert [len(rows) for _, rows in copies] == [1, 1]


def test_ccd_identity_requires_matching_heavy_atom_names_and_elements():
    ccd = """data_ZN
loop_
_chem_comp_atom.atom_id
_chem_comp_atom.type_symbol
_chem_comp_atom.charge
ZN Zn 2
"""
    line = _hetatm(1, "ZN", "ZN", "A", 1450, "ZN")
    assert multisite._validate_identity([line], ccd, "zinc")["ZN"] == {"element": "ZN", "charge": 2}
    with pytest.raises(ValueError, match="identity mismatch"):
        multisite._validate_identity([_hetatm(1, "BAD", "ZN", "A", 1450, "ZN")], ccd, "zinc")


def test_selected_zinc_is_prepared_separately_with_ccd_charge(monkeypatch, tmp_path):
    ccd = """data_ZN
loop_
_chem_comp_atom.atom_id
_chem_comp_atom.type_symbol
_chem_comp_atom.charge
ZN Zn 2
"""
    line = _hetatm(10, "ZN", "ZN", "A", 1450, "ZN")
    monkeypatch.setattr(multisite, "_fetch_ccd", lambda component: ccd)
    receptor, audit = multisite._append_selected_cofactors(line, "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  0.00  0.00     0.000 C\n",
                                                           ("A:1450:ZN",), tmp_path)
    assert audit == [{"selection": "A:1450:ZN", "ccd_atom_count": 1,
                      "atom_identity_validated": True, "element": "ZN", "formal_charge": 2}]
    assert receptor.rstrip().endswith("2.000 Zn")
    assert (tmp_path / "cofactor-ZN.cif").read_text() == ccd


@pytest.mark.parametrize("label", ["Estimated Free Energy of Binding", "Affinity"])
def test_vinardo_parser_accepts_supported_vina_labels(label):
    assert multisite.parse_vinardo_score(f"{label} : -7.125 kcal/mol") == pytest.approx(-7.125)


def test_vinardo_parser_does_not_invent_missing_score():
    with pytest.raises(ValueError, match="missing"):
        multisite.parse_vinardo_score("Search completed without a score")


def test_search_completion_accepts_fewer_than_requested_distinct_modes():
    candidates = [{"rank": rank} for rank in range(1, 6)]
    rows = [{"pocket_rank": rank, "original_model": model}
            for rank in range(1, 6) for model in range(1, 10 if rank < 5 else 6)]
    assert multisite._search_complete(candidates, rows, [])
    assert not multisite._search_complete(candidates, rows[:-5], [])
    assert not multisite._search_complete(candidates, rows, [{"pocket_rank": 3, "error": "timeout"}])


def test_vinardo_scoring_grid_covers_pose_with_local_receptor_margin():
    pose = "\n".join([
        "ATOM      1  C1  LIG A   1      20.000  30.000  40.000  1.00  0.00     0.000 C",
        "ATOM      2  C2  LIG A   1      24.000  32.000  41.000  1.00  0.00     0.000 C",
    ])
    grid = multisite._pose_scoring_grid(pose, {"center": [0, 0, 0], "size": [16, 16, 16]})
    assert grid["center"] == [22, 31, 40.5]
    assert grid["size"] == [16, 16, 16]
    assert grid["margin_angstrom"] == 6


def test_ligand_aware_grid_grows_dimensions_to_cover_ccd_span():
    from rdkit import Chem
    from rdkit.Geometry import Point3D
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCC"))
    conformer = Chem.Conformer(molecule.GetNumAtoms())
    for index in range(molecule.GetNumAtoms()):
        conformer.SetAtomPosition(index, Point3D(float(index * 3), float(index % 2), 0.0))
    molecule.AddConformer(conformer)
    grid = multisite._ligand_aware_grid(
        {"rank": 2, "center": [1, 2, 3], "size": [12, 22, 14]}, molecule)
    assert grid["center"] == [1, 2, 3]
    assert grid["size"] == [14, 22, 14]
    assert grid["required_size_angstrom"] == [14.0, 9.0, 8.0]


def test_ligand_aware_grid_fails_if_ligand_cannot_fit_supported_grid():
    from rdkit import Chem
    from rdkit.Geometry import Point3D
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCCCCCCC"))
    conformer = Chem.Conformer(molecule.GetNumAtoms())
    for index in range(molecule.GetNumAtoms()):
        conformer.SetAtomPosition(index, Point3D(float(index * 5), 0.0, 0.0))
    molecule.AddConformer(conformer)
    with pytest.raises(ValueError, match="exceeding 40"):
        multisite._ligand_aware_grid({"rank": 1, "center": [0, 0, 0], "size": [16] * 3}, molecule)
