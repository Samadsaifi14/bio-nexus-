from app.services.docking_pose_analytics import cluster_poses, pose_rmsd_matrix, water_mediated_interactions

PDBQT = """MODEL 1
HETATM    1  O1  LIG A   1       4.000   0.000   0.000  1.00  0.00           O
HETATM    2  C1  LIG A   1       5.000   0.000   0.000  1.00  0.00           C
ENDMDL
MODEL 2
HETATM    1  O1  LIG A   1       4.500   0.000   0.000  1.00  0.00           O
HETATM    2  C1  LIG A   1       5.500   0.000   0.000  1.00  0.00           C
ENDMDL
MODEL 3
HETATM    1  O1  LIG A   1      10.000   0.000   0.000  1.00  0.00           O
HETATM    2  C1  LIG A   1      11.000   0.000   0.000  1.00  0.00           C
ENDMDL
"""

PDB_WITH_WATER = """ATOM      1  N   LYS A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  LYS A   1      -1.000   0.000   0.000  1.00 20.00           C
HETATM    3  O   HOH A 101       2.000   0.000   0.000  1.00 20.00           O
END
"""


def test_pairwise_pose_rmsd_is_symmetric_and_zero_on_diagonal():
    result = pose_rmsd_matrix(PDBQT)
    matrix = result["matrix_angstrom"]
    assert result["models"] == [1, 2, 3]
    assert matrix[0][0] == 0.0
    assert matrix[0][1] == matrix[1][0] == 0.5
    assert result["symmetry_corrected"] is False


def test_pose_clustering_separates_distant_pose():
    result = cluster_poses(PDBQT, cutoff_angstrom=2.0)
    assert result["cluster_count"] == 2
    memberships = [set(c["models"]) for c in result["clusters"]]
    assert {1, 2} in memberships
    assert {3} in memberships


def test_water_bridge_is_geometric_and_heuristic():
    result = water_mediated_interactions(PDB_WITH_WATER, PDBQT, cutoff_angstrom=3.5)
    assert result["status"] == "OBSERVED"
    assert result["bridge_count"] >= 1
    assert result["evidence_class"] == "Heuristic"
    assert "Geometry alone" in result["limitation"]


def test_water_screen_covers_every_pose_and_retains_atom_identity():
    result = water_mediated_interactions(PDB_WITH_WATER, PDBQT)
    assert result["pose_count"] == 3
    summaries = {p["model"]: p for p in result["poses"]}
    assert summaries[1]["bridge_count"] == 1
    assert summaries[2]["bridge_count"] == 1
    assert summaries[3]["bridge_count"] == 0
    assert {b["model"] for b in result["bridges"]} == {1, 2}
    assert result["bridges"][0]["water_identity"] == "A:HOH101:O"
    reordered = PDBQT.replace("           O", "           X").replace("           C", "           O").replace("           X", "           C")
    assert water_mediated_interactions(PDB_WITH_WATER, reordered)["bridges"][0]["ligand_polar_atom_index"] == 2


def test_autodock_atom_types_and_heavy_atom_rmsd():
    from app.services.docking_pose_analytics import _element
    assert _element("HETATM    1  O1  LIG A   1       4.000   0.000   0.000  1.00  0.00    -0.300 OA") == "O"
    hydrogen = "HETATM    3  H1  LIG A   1       0.000   0.000   0.000  1.00  0.00           H"
    first = PDBQT.split("ENDMDL")[0] + "\n" + hydrogen + "\nENDMDL\n"
    second = first.replace("MODEL 1", "MODEL 2").replace("H1  LIG A   1       0.000", "H1  LIG A   1      20.000")
    result = pose_rmsd_matrix(first + second)
    assert result["matrix_angstrom"][0][1] == 0.0
    assert result["hydrogens_excluded"] is True


def test_water_evidence_hashes_inputs_and_distinguishes_missing_receptor():
    import hashlib
    result = water_mediated_interactions(PDB_WITH_WATER, PDBQT)
    assert result["provenance"]["original_pdb_sha256"] == hashlib.sha256(PDB_WITH_WATER.encode()).hexdigest()
    assert water_mediated_interactions("", PDBQT)["status"] == "UNAVAILABLE"
    no_water = "\n".join(l for l in PDB_WITH_WATER.splitlines() if "HOH" not in l)
    result = water_mediated_interactions(no_water, PDBQT)
    assert result["status"] == "NOT_OBSERVED"
    assert len(result["poses"]) == 3
