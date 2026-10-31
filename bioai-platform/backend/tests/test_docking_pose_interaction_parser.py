"""Regression tests for Vina pose parsing and partial interaction failures.

These tests exercise the PDBQT record/model parser independently of chemistry.
They deliberately mock the chemistry routine: they validate parser behavior,
not the scientific validity of interaction classifications.
"""
import asyncio

from app.routers import docking as module


def _atom(record="ATOM", serial=1, atom="C1"):
    return (
        f"{record:<6}{serial:5d} {atom:<4s} LIG A   1    "
        f"{1.0:8.3f}{2.0:8.3f}{3.0:8.3f}  1.00  0.00"
    )


def test_vina_atom_records_are_parsed_as_pose_atoms(monkeypatch):
    observed = []

    def fake_compute(protein, ligand, ligand_smiles=None):
        observed.append(ligand)
        return {"hbonds": [], "hydrophobic": [], "pi_stacking": [], "salt_bridges": []}

    monkeypatch.setattr(module, "_compute_interactions", fake_compute)
    result = module._summarize_pose_interactions("protein", _atom("ATOM") + "\n")

    assert result == [{"model": 1, "hbonds": 0, "hydrophobic": 0, "pi_stacking": 0, "salt_bridges": 0}]
    assert len(observed) == 1
    assert observed[0].startswith("ATOM")


def test_heteroatom_records_are_also_parsed(monkeypatch):
    observed = []
    monkeypatch.setattr(
        module, "_compute_interactions",
        lambda protein, ligand, ligand_smiles=None: observed.append(ligand) or {
            "hbonds": [], "hydrophobic": [], "pi_stacking": [], "salt_bridges": []
        },
    )
    result = module._summarize_pose_interactions("protein", _atom("HETATM") + "\n")
    assert len(result) == 1
    assert observed[0].startswith("HETATM")


def test_multiple_models_remain_separate(monkeypatch):
    observed = []
    monkeypatch.setattr(
        module, "_compute_interactions",
        lambda protein, ligand: observed.append(ligand) or {
            "hbonds": [], "hydrophobic": [], "pi_stacking": [], "salt_bridges": []
        },
    )
    pdbqt = "MODEL 1\n" + _atom("ATOM", 1) + "\nENDMDL\nMODEL 2\n" + _atom("ATOM", 2) + "\nENDMDL\n"
    result = module._summarize_pose_interactions("protein", pdbqt)
    assert [row["model"] for row in result] == [1, 2]
    assert len(observed) == 2


def test_single_pose_without_model_delimiters_is_supported(monkeypatch):
    monkeypatch.setattr(
        module, "_compute_interactions",
        lambda protein, ligand: {"hbonds": [], "hydrophobic": [], "pi_stacking": [], "salt_bridges": []},
    )
    result = module._summarize_pose_interactions("protein", _atom("ATOM") + "\n")
    assert len(result) == 1
    assert result[0]["model"] == 1


def test_empty_models_are_not_reported_as_zero_contact_poses(monkeypatch):
    monkeypatch.setattr(
        module, "_compute_interactions",
        lambda *args: (_ for _ in ()).throw(AssertionError("chemistry must not run for an empty pose")),
    )
    pdbqt = "MODEL 1\nENDMDL\nMODEL 2\n" + _atom("ATOM") + "\nENDMDL\n"
    result = module._summarize_pose_interactions("protein", pdbqt)
    assert [row["model"] for row in result] == [2]



def test_stored_job_pose_extractor_preserves_model_ids_affinities_and_atom_records():
    pdbqt = (
        "MODEL 1\n"
        "REMARK VINA RESULT:    -5.132      0.000      0.000\n"
        + _atom("ATOM", 1) + "\nENDMDL\n"
        "MODEL 2\n"
        "REMARK VINA RESULT:    -4.981      1.234      2.345\n"
        + _atom("ATOM", 2) + "\nENDMDL\n"
    )
    models = module._extract_vina_pose_models(pdbqt)
    assert [m["model"] for m in models] == [1, 2]
    assert [m["affinity_kcal_mol"] for m in models] == [-5.132, -4.981]
    assert all(len(m["records"]) == 1 for m in models)



def test_exact_job_reproduction_returns_all_poses_without_mutating_artifact(monkeypatch):
    original = {
        "pdb_id": "4HHB",
        "smiles": "CCO",
        "vina_version": "1.2.7",
        "vina_exhaustiveness": 32,
        "vina_num_modes": 2,
        "vina_seed": 42,
        "box_center": [0.0, 0.0, 0.0],
        "box_size": [20.0, 20.0, 20.0],
        "receptor_pdb": "ATOM\n",
        "result_pdbqt": (
            "MODEL 1\nREMARK VINA RESULT: -5.132 0.0 0.0\n" + _atom("ATOM", 1) + "\nENDMDL\n"
            "MODEL 2\nREMARK VINA RESULT: -4.981 0.0 0.0\n" + _atom("ATOM", 2) + "\nENDMDL\n"
        ),
        "interaction_analysis": {"status": "UNAVAILABLE", "reason": "ValueError"},
    }
    monkeypatch.setattr(module, "_load_docking_result", lambda job_id, user_id: original)
    monkeypatch.setattr(
        module, "_compute_interactions",
        lambda protein, ligand, smiles: {
            "status": "COMPUTED", "engine": "RDKit", "engine_version": "test",
            "counts": {"hbonds": 1, "hydrophobic": 0, "pi_stacking": 0, "salt_bridges": 0},
            "hbonds": [{"type": "hbond"}], "hydrophobic": [], "pi_stacking": [], "salt_bridges": [],
            "protein_parse": {"residues_skipped": []}, "limitations": [],
        },
    )
    result = asyncio.run(module.recalculate_stored_docking_interactions("job-1", "user-1"))
    assert result["status"] == "COMPUTED"
    assert result["pose_count"] == 2
    assert [p["affinity_kcal_mol"] for p in result["pose_results"]] == [-5.132, -4.981]
    assert result["reproduction"]["original_artifact_mutated"] is False
    assert original["interaction_analysis"]["status"] == "UNAVAILABLE"
