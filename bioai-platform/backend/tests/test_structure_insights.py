from app.routers.structure_insights import contact_map, interface_analysis, mutation_context, surface_analysis

PDB = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   ALA A   1       2.000   0.000   0.000  1.00 20.00           C
ATOM      4  N   LYS A   2       3.000   0.000   0.000  1.00 20.00           N
ATOM      5  CA  LYS A   2       4.000   0.000   0.000  1.00 20.00           C
ATOM      6  C   LYS A   2       5.000   0.000   0.000  1.00 20.00           C
ATOM      7  N   ASP B   1       4.000   3.000   0.000  1.00 20.00           N
ATOM      8  CA  ASP B   1       4.000   4.000   0.000  1.00 20.00           C
ATOM      9  C   ASP B   1       4.000   5.000   0.000  1.00 20.00           C
END
"""


def test_contact_map_is_distance_bounded():
    result = contact_map(PDB, cutoff=5.0)
    assert result["residue_count"] == 3
    assert result["contact_count"] >= 2
    assert all(c["distance_angstrom"] <= 5.0 for c in result["contacts"])


def test_interface_analysis_only_reports_cross_chain_contacts():
    result = interface_analysis(PDB, cutoff=5.0)
    assert result["interfaces"]
    top = result["interfaces"][0]
    assert top["chains"] == ["A", "B"]
    assert top["interface_residue_count"] >= 2


def test_mutation_mapping_does_not_infer_effect():
    result = mutation_context(PDB, "A", 2, "E", radius=6.0)
    assert result["mapping_status"] == "mapped"
    assert result["mutation"] == "K2E"
    assert "No energetic or pathogenicity effect" in result["interpretation"]
    assert result["neighbours"]


def test_surface_analysis_labels_electrostatics_as_heuristic():
    result = surface_analysis(PDB)
    assert result["total_sasa_angstrom2"] > 0
    patch = result["charge_patch_heuristic"]
    assert patch["evidence_class"] == "Heuristic"
    assert "Not an electrostatic potential" in patch["limitation"]
