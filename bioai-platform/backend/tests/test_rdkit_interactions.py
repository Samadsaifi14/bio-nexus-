"""Known-structure and fail-closed tests for the RDKit docking interaction engine."""
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from app.services.rdkit_interactions import calculate_interactions, _ligand_with_template, _ligand_pose_from_pdbqt


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
        line = line[:17] + f"{residue:>3s}" + f" {chain}{residue_number:4d} " + line[27:]
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



def test_original_pdbqt_pose_mapping_preserves_coordinates_and_atom_order():
    smiles = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
    template = Chem.MolFromSmiles(smiles)
    pdbqt = """MODEL 1
ATOM      1  C   UNL     1       2.527  21.519  40.083  0.00  0.00    +0.013 C
ATOM      2  N   UNL     1       3.003  20.632  39.050  0.00  0.00    -0.328 N
ATOM      3  C   UNL     1       3.988  20.924  38.140  0.00  0.00    +0.099 A
ATOM      4  N   UNL     1       4.207  19.912  37.321  0.00  0.00    -0.218 NA
ATOM      5  C   UNL     1       3.329  18.951  37.723  0.00  0.00    +0.168 A
ATOM      6  C   UNL     1       2.575  19.363  38.781  0.00  0.00    +0.151 A
ATOM      7  C   UNL     1       1.580  18.553  39.387  0.00  0.00    +0.282 A
ATOM      8  O   UNL     1       0.871  18.940  40.312  0.00  0.00    -0.265 OA
ATOM      9  N   UNL     1       1.490  17.281  38.816  0.00  0.00    -0.262 N
ATOM     10  C   UNL     1       2.216  16.833  37.698  0.00  0.00    +0.333 A
ATOM     11  O   UNL     1       2.010  15.718  37.210  0.00  0.00    -0.246 OA
ATOM     12  N   UNL     1       3.169  17.703  37.166  0.00  0.00    -0.280 N
ATOM     13  C   UNL     1       3.975  17.286  36.032  0.00  0.00    +0.018 C
ATOM     14  C   UNL     1       0.498  16.378  39.367  0.00  0.00    +0.020 C
ENDMDL
"""
    pose = _ligand_pose_from_pdbqt(pdbqt, template)
    assert pose.GetNumHeavyAtoms() == 14
    assert pose.GetConformer().GetAtomPosition(0).x == pytest.approx(2.527)
    assert pose.GetConformer().GetAtomPosition(13).z == pytest.approx(39.367)


def test_original_pdbqt_mapping_rejects_atom_order_mismatch():
    template = Chem.MolFromSmiles("CCO")
    pdbqt = """ATOM      1  O   UNL     1       0.000   0.000   0.000  0.00  0.00 O
ATOM      2  C   UNL     1       1.000   0.000   0.000  0.00  0.00 C
ATOM      3  C   UNL     1       2.000   0.000   0.000  0.00  0.00 C
"""
    with pytest.raises(ValueError, match="atom sequence"):
        _ligand_pose_from_pdbqt(pdbqt, template)
