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
