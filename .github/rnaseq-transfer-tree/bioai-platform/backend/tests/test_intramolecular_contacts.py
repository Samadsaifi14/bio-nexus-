"""Contract tests for intramolecular contact analysis.

A bare receptor PDB (structure-prep / CASTp) has no ligand, so ligand-style
contacts do not apply. These tests pin the geometry criteria, the covalent
neighbour exclusion, the truncation contract, and the guarantee that an analysis
failure is never rendered as "no contacts found".
"""

import pytest

from app.tools.contacts import (
    DISULFIDE_MAX_DISTANCE,
    HBOND_MAX_DISTANCE,
    MAX_PER_TYPE,
    SALT_BRIDGE_MAX_DISTANCE,
    compute_intramolecular_contacts,
)


def _atom(name, res_name, chain, res_seq, x, y, z, element=None):
    """Emit a fixed-width PDB ATOM record: chain at col 22, resSeq at cols 23-26."""
    element = element or name[0]
    return (
        "ATOM  " + f"{1:5d}" + " " + f"{name:<4s}" + " " + f"{res_name:>3s}"
        + " " + f"{chain:1s}" + f"{res_seq:4d}" + " " + "   "
        + f"{x:8.3f}{y:8.3f}{z:8.3f}" + "  1.00  0.00" + "          " + f"{element:>2s}"
        + "\n"
    )


def _pdb(*atoms):
    return "".join(atoms) + "END\n"


def test_hydrogen_bond_detected_within_cutoff():
    # Non-adjacent residues (1 and 5) so the covalent exclusion does not apply.
    pdb = _pdb(
        _atom("N", "SER", "A", 1, 0.0, 0.0, 0.0),
        _atom("O", "THR", "A", 5, 2.9, 0.0, 0.0),
    )
    result = compute_intramolecular_contacts(pdb)
    assert result["hbonds"]["count"] == 1
    assert result["hbonds"]["items"][0]["distance"] == pytest.approx(2.9, abs=0.01)


def test_hydrogen_bond_rejected_beyond_cutoff():
    pdb = _pdb(
        _atom("N", "SER", "A", 1, 0.0, 0.0, 0.0),
        _atom("O", "THR", "A", 5, HBOND_MAX_DISTANCE + 0.5, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(pdb)["hbonds"]["count"] == 0


def test_adjacent_residues_excluded_as_covalent_neighbours():
    # Ser1 O and Thr2 N are 1.5 A apart but are peptide-bond neighbours.
    pdb = _pdb(
        _atom("O", "SER", "A", 1, 0.0, 0.0, 0.0),
        _atom("N", "THR", "A", 2, 1.5, 0.0, 0.0),
    )
    result = compute_intramolecular_contacts(pdb)
    assert result["hbonds"]["count"] == 0
    assert result["hydrophobic"]["count"] == 0


def test_same_residue_atoms_excluded():
    pdb = _pdb(
        _atom("N", "SER", "A", 7, 0.0, 0.0, 0.0),
        _atom("O", "SER", "A", 7, 2.0, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(pdb)["hbonds"]["count"] == 0


def test_salt_bridge_requires_opposite_charged_groups():
    pdb = _pdb(
        _atom("NZ", "LYS", "A", 11, 0.0, 0.0, 0.0),
        _atom("OE1", "GLU", "A", 34, 3.5, 0.0, 0.0),
    )
    result = compute_intramolecular_contacts(pdb)
    assert result["salt_bridges"]["count"] == 1
    assert result["salt_bridges"]["items"][0]["charge_pair"] == "LYS+ / GLU-"
    # The same atoms are also a polar contact, but salt bridges must not be
    # double-counted as hydrophobic.
    assert result["hydrophobic"]["count"] == 0


def test_salt_bridge_beyond_cutoff_rejected():
    pdb = _pdb(
        _atom("NZ", "LYS", "A", 11, 0.0, 0.0, 0.0),
        _atom("OE1", "GLU", "A", 34, SALT_BRIDGE_MAX_DISTANCE + 0.5, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(pdb)["salt_bridges"]["count"] == 0


def test_disulfide_bridge_detected():
    pdb = _pdb(
        _atom("SG", "CYS", "A", 3, 0.0, 0.0, 0.0),
        _atom("SG", "CYS", "A", 14, 2.0, 0.0, 0.0),
    )
    result = compute_intramolecular_contacts(pdb)
    assert result["disulfides"]["count"] == 1
    assert result["disulfides"]["items"][0]["distance"] == pytest.approx(2.0, abs=0.01)
    # A covalent bond must not also appear as a non-covalent contact.
    assert result["hbonds"]["count"] == 0


def test_disulfide_beyond_cutoff_rejected():
    pdb = _pdb(
        _atom("SG", "CYS", "A", 3, 0.0, 0.0, 0.0),
        _atom("SG", "CYS", "A", 14, DISULFIDE_MAX_DISTANCE + 0.5, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(pdb)["disulfides"]["count"] == 0


def test_hydrophobic_contact_only_for_apolar_residues():
    pdb = _pdb(
        _atom("CB", "LEU", "A", 2, 0.0, 0.0, 0.0),
        _atom("CG1", "VAL", "A", 40, 3.5, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(pdb)["hydrophobic"]["count"] == 1

    charged = _pdb(
        _atom("CB", "LEU", "A", 2, 0.0, 0.0, 0.0),
        _atom("CG1", "LYS", "A", 40, 3.5, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(charged)["hydrophobic"]["count"] == 0


def test_payload_reports_criteria_and_limitation():
    result = compute_intramolecular_contacts(_pdb(_atom("N", "SER", "A", 1, 0.0, 0.0, 0.0)))
    assert result["method"]["kind"] == "intramolecular"
    assert result["method"]["criteria"]["hydrogen_bond"]["max_distance_angstrom"] == HBOND_MAX_DISTANCE
    assert result["method"]["explicit_hydrogens"] is False
    assert "energetics" in result["limitation"].lower()
    for key in ("hbonds", "salt_bridges", "hydrophobic", "disulfides"):
        assert set(result[key]) >= {"items", "count", "total", "truncated"}


def test_four_digit_residue_numbers_parse():
    # With 4-digit resSeq the chain ID abuts the number ("A1000"), so the parser
    # must not require a blank column between them.
    pdb = _pdb(
        _atom("N", "SER", "A", 1000, 0.0, 0.0, 0.0),
        _atom("O", "THR", "A", 1005, 2.9, 0.0, 0.0),
    )
    assert compute_intramolecular_contacts(pdb)["hbonds"]["count"] == 1


def test_empty_input_returns_zero_counts_not_error():
    result = compute_intramolecular_contacts("")
    for key in ("hbonds", "salt_bridges", "hydrophobic", "disulfides"):
        assert result[key]["count"] == 0
        assert result[key]["truncated"] is False


def test_truncation_is_flagged_rather_than_silent():
    # LEU CB every 4.0 A (<= the 4.5 A cutoff) with non-adjacent sequence
    # numbers, so the covalent-neighbour exclusion does not remove the pairs.
    rows = []
    n = MAX_PER_TYPE + 50
    for idx in range(n):
        rows.append(_atom("CB", "LEU", "A", 1000 + idx * 2, 0.0, 0.0, float(idx) * 4.0))
    result = compute_intramolecular_contacts(_pdb(*rows))
    assert result["hydrophobic"]["truncated"] is True
    assert result["hydrophobic"]["count"] == MAX_PER_TYPE
    assert result["hydrophobic"]["total"] > MAX_PER_TYPE


def test_explicit_hydrogens_enable_angle_criterion():
    # Donor N and acceptor O 2.8 A apart, but the attached H points perpendicular
    # to the N...O axis, so the D-H...A angle is ~70 deg and must be rejected.
    pdb = _pdb(
        _atom("N", "SER", "A", 1, 0.0, 0.0, 0.0),
        _atom("H", "SER", "A", 1, 0.0, 1.0, 0.0),
        _atom("O", "THR", "A", 5, 2.8, 0.0, 0.0),
    )
    result = compute_intramolecular_contacts(pdb)
    assert result["method"]["explicit_hydrogens"] is True
    assert result["hbonds"]["count"] == 0


def test_explicit_hydrogens_accept_linear_geometry():
    # Same pair with a linear D-H...A arrangement (~180 deg) must be kept.
    pdb = _pdb(
        _atom("N", "SER", "A", 1, 0.0, 0.0, 0.0),
        _atom("H", "SER", "A", 1, 1.0, 0.0, 0.0),
        _atom("O", "THR", "A", 5, 2.8, 0.0, 0.0),
    )
    result = compute_intramolecular_contacts(pdb)
    assert result["hbonds"]["count"] == 1
    assert result["hbonds"]["items"][0]["geometry"] == "donor_h_acceptor_angle"
