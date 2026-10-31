"""Known-structure and fail-closed tests for the RDKit docking interaction engine."""
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from app.services.rdkit_interactions import calculate_interactions, _ligand_with_template


def _embedded_pdb(smiles, residue="LIG", chain="A", residue_number=1):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(mol, randomSeed=17) == 0
    AllChem.UFFOptimizeMolecule(mol, maxIters=100)
    block = Chem.MolToPDBBlock(mol)
    lines = []
    serial = 1
    for line in block.splitlines():
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        line = line[:17] + f"{residue:>3s}" + f" {chain}{residue_number:4d}" + line[27:]
        line = line[:6] + f"{serial:5d}" + line[11:]
        lines.append(line)
        serial += 1
    return "\n".join(lines) + "\nEND\n"


def test_ligand_pose_is_assigned_bond_orders_from_submitted_smiles():
    pdb = _embedded_pdb("c1ccccc1")
    mol = _ligand_with_template(pdb, "c1ccccc1")
    assert mol.GetNumHeavyAtoms() == 6
    assert sum(1 for bond in mol.GetBonds() if bond.GetIsAromatic()) == 6


def test_atom_count_mismatch_fails_closed():
    pdb = _embedded_pdb("CCO")
    with pytest.raises(ValueError, match="atom count does not match"):
        _ligand_with_template(pdb, "c1ccccc1")


def test_invalid_smiles_fails_closed():
    pdb = _embedded_pdb("CCO")
    with pytest.raises(ValueError, match="SMILES"):
        _ligand_with_template(pdb, "not-a-smiles")


def test_rdkit_result_has_provenance_and_explicit_thresholds():
    protein = _embedded_pdb("NCC(=O)O", residue="GLY", residue_number=1)
    ligand = _embedded_pdb("CCO")
    result = calculate_interactions(protein, ligand, "CCO")
    assert result["status"] == "COMPUTED"
    assert result["engine"] == "RDKit"
    assert result["engine_version"]
    assert result["thresholds"]["hbond_distance_angstrom"] == 3.5
    assert set(result["counts"]) == {"hbonds", "hydrophobic", "pi_stacking", "salt_bridges"}
    assert all(isinstance(result[key], list) for key in result["counts"])


def test_missing_protein_atoms_is_not_reported_as_zero_contacts():
    with pytest.raises(ValueError, match="no PDB atom records"):
        calculate_interactions("END\n", _embedded_pdb("CCO"), "CCO")


def test_missing_ligand_atoms_is_not_reported_as_zero_contacts():
    with pytest.raises(ValueError, match="no PDB atom records"):
        calculate_interactions(_embedded_pdb("NCC(=O)O", residue="GLY"), "END\n", "CCO")
