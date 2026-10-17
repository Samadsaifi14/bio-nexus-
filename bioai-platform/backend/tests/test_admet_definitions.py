"""Explicit ADMET descriptor definitions; compare distinct graph properties."""
from app.tools.admet import compute_descriptors


def test_chemical_acceptors_are_distinct_from_lipinski_atom_count():
    result = compute_descriptors("CC(=O)OC1=CC=CC=C1C(=O)O")
    assert result["hba"] == 3
    assert result["lipinski_n_o_count"] == 4
    assert result["hbd"] == 1


def test_nitrogen_count_is_not_automatically_an_acceptor_count():
    result = compute_descriptors("C[N+](C)(C)C")
    assert result["hba"] == 0
    assert result["lipinski_n_o_count"] == 1
