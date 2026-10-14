"""Regression coverage for docking artifact formats and fpocket evidence parsing."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools import docking


def test_fpocket_descriptors_are_parsed_as_reported_values():
    parsed = docking._parse_fpocket_descriptors("""
Pocket 1 :
Pocket Score : 12.5
Druggability Score : 0.72
Number of alpha spheres : 34
Volume : 184.25
Surface Area : 95.5
Pocket 2 :
Score : 7.0
""")

    assert parsed[1] == {
        "score": 12.5,
        "druggability_score": 0.72,
        "number_of_alpha_spheres": 34,
        "volume": 184.25,
        "area": 95.5,
    }
    assert parsed[2] == {"score": 7.0}


def test_pdbqt_sdf_conversion_keeps_every_pose_and_vina_metrics(monkeypatch):
    sdf_text = "ligand\n  Open Babel\n\n  1  0  0  0  0  0            999 V2000\nM  END\n$$$$\n"

    def fake_run(command, **_kwargs):
        Path(command[3]).write_text(sdf_text)
        return SimpleNamespace(returncode=0, stderr="", stdout="1 molecule converted")

    monkeypatch.setattr(docking, "_ensure_obabel", lambda: "obabel-test")
    monkeypatch.setattr(docking.subprocess, "run", fake_run)

    converted = docking.pdbqt_to_sdf(
        "MODEL 1\nHETATM ligand atoms\nENDMDL\nMODEL 2\nHETATM ligand atoms\nENDMDL\n",
        [
            {"model": 1, "affinity": -7.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"model": 2, "affinity": -6.8, "rmsd_lb": 1.1, "rmsd_ub": 1.7},
        ],
    )

    assert converted.count("$$$$") == 2
    assert converted.count("V2000") == 2
    assert "VINA_SCORE_KCAL_PER_MOL" in converted
    assert "-7.2" in converted and "-6.8" in converted
    assert "MODEL 1" not in converted


def test_fpocket_grid_uses_real_candidate_files_and_reports_metadata(tmp_path, monkeypatch):
    executable = tmp_path / "fpocket"
    executable.write_text("test executable placeholder")
    monkeypatch.setattr("app.tools.structure_prep.FPOCKET_BIN", str(executable))

    def fake_fpocket(command, **_kwargs):
        input_path = Path(command[-1])
        out = input_path.parent / f"{input_path.stem}_out"
        pockets = out / "pockets"
        pockets.mkdir(parents=True)
        (out / "info").mkdir()
        (out / "info" / "infos.txt").write_text(
            "Pocket 1 :\nPocket Score : 12.5\nDruggability Score : 0.72\nVolume : 184.25\n"
        )
        lines = []
        for i in range(1, 7):
            lines.append(
                f"ATOM  {i:5d}  CA  GLY A{i:4d}    {i * 1.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C"
            )
        (pockets / "pocket1_atm.pdb").write_text("\n".join(lines) + "\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(docking.subprocess, "run", fake_fpocket)
    result = docking.compute_pocket_grid(
        "ATOM      1  CA  GLY A   1       1.000   0.000   0.000  1.00 20.00           C\n"
    )

    assert result["selected_rank"] == 1
    assert result["candidates"][0]["score"] == 12.5
    assert result["candidates"][0]["druggability_score"] == 0.72
    assert result["candidates"][0]["residues"]
    assert all(size <= 32 for size in result["size"])
