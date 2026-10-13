"""CASTp pocket-analysis provenance: explicit method chain, fallback attribution,
DEGRADED for heuristic output, FAILED when no engine produces a result."""

import shutil
from pathlib import Path

from app.tools.castp import _parse_fpocket


def _sample_pdb() -> str:
    return (
        "ATOM      1  N   ALA A   1      -1.000  -1.000  -1.000  1.00 20.00           N\n"
        "ATOM      2  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
        "ATOM      3  C   ALA A   1       1.000   1.000   1.000  1.00 20.00           C\n"
        "ATOM      4  O   ALA A   1       2.000   2.000   2.000  1.00 20.00           O\n"
    )


class _ExecLoop:
    """Fake running loop that executes run_in_executor callables inline."""

    async def run_in_executor(self, _pool, fn, *args):
        return fn(*args)


async def test_fpocket_path_when_engine_available(monkeypatch):
    import app.tools.castp as m

    fake_pockets = [{
        "id": 1, "druggability_score": 0.66, "volume": 100.0, "area_sa": 50.0,
        "score": 0.3, "num_residues": 5, "centroid": [1.0, 1.0, 1.0], "radius": 3.1,
        "residues": ["A1ALA"],
    }]

    def fake_fpocket_run(fpocket, pdb_text, pdb_id, probe_radius):
        return {
            "pdb_id": pdb_id,
            "probe_radius": probe_radius,
            "total_residues": 1,
            "method": "fpocket",
            "pockets": fake_pockets,
        }

    monkeypatch.setattr(m, "FPOCKET_BIN", "C:/fake/fpocket.exe")
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(m, "_run_fpocket_analysis", fake_fpocket_run)
    loop = _ExecLoop()
    monkeypatch.setattr(m.asyncio, "get_running_loop", lambda: loop)

    result = await m._analyze_pockets(_sample_pdb(), "TEST", 1.4)
    assert result["method"] == "fpocket"
    assert result["fallback_used"] is False
    assert result["pockets"] == fake_pockets
    assert result["methods_tried"] == [{"method": "fpocket", "status": "ok"}]



async def test_unavailable_fpocket_does_not_substitute_heuristic(monkeypatch):
    import app.tools.castp as m
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    def forbidden(*args):
        raise AssertionError("Heuristic must be explicitly selected")
    monkeypatch.setattr(m, "_analyze_pockets_sasa_sync", forbidden)
    result = await m._analyze_pockets(_sample_pdb(), "TEST", 1.4)
    assert result["status"] == "FAILED"
    assert result["method"] == "fpocket"
    assert result["fallback_used"] is False
    assert result["pockets"] == []


async def test_explicit_heuristic_is_labelled(monkeypatch):
    import app.tools.castp as m
    result = await m._analyze_pockets(_sample_pdb(), "TEST", 1.4, method="sasa_heuristic")
    assert result["evidence_class"] == "Heuristic"
    assert "SASA heuristic" in result["method"]
    assert result["fallback_used"] is False


def test_fpocket_parse_reads_real_output(tmp_path):
    out_dir = tmp_path / "input_out"
    info = out_dir / "info"
    pockets_dir = out_dir / "pockets"
    info.mkdir(parents=True)
    pockets_dir.mkdir()

    (info / "infos.txt").write_text(
        "Pocket 1\n"
        "Druggability Score: 0.66\n"
        "Volume: 123.4\n"
        "Area: 456.7\n"
        "Score: 0.31\n"
        "Number of residues: 8\n"
        "\n"
        "Pocket 2\n"
        "Druggability Score: 0.12\n"
        "Volume: 50.0\n"
        "Area: 80.0\n"
        "Score: 0.10\n"
        "Number of residues: 4\n"
    )
    (pockets_dir / "pocket1_atm.pdb").write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
    )
    (pockets_dir / "pocket2_atm.pdb").write_text(
        "ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00 20.00           C\n"
    )

    result = _parse_fpocket(out_dir, "1TIM", 1.4)
    assert result["method"] == "fpocket"
    assert [p["id"] for p in result["pockets"]] == [1, 2]
    assert result["pockets"][0]["volume_sa"] == 123.4
    assert result["pockets"][0]["area_sa"] == 456.7
    assert result["pockets"][0]["centroid"] == [0.0, 0.0, 0.0]
    assert result["pockets"][1]["volume_sa"] == 50.0
    assert result["pockets"][1]["area_sa"] == 80.0
    assert result["pockets"][1]["centroid"] == [1.0, 1.0, 1.0]


def test_missing_fpocket_metrics_are_not_zero(tmp_path):
    (tmp_path / "input_info.txt").write_text("Pocket 1\nScore: 0.3\n")
    pocket = _parse_fpocket(tmp_path, "TEST", 1.4)["pockets"][0]
    assert pocket["volume_sa"] is None
    assert pocket["area_sa"] is None
    assert pocket["radius"] is None
    assert pocket["centroid"] is None


def test_structure_prep_reads_native_fpocket_file_and_preserves_missing(tmp_path):
    from app.tools.structure_prep import _parse_fpocket_output
    (tmp_path / "input_info.txt").write_text("Pocket 1\nDruggability Score: 0.2\nVolume: 100.0\n")
    result = _parse_fpocket_output(tmp_path, "native output")
    assert result.status == "complete"
    assert result.pockets[0]["volume"] == 100.0
    assert result.pockets[0]["area"] is None
    assert result.pockets[0]["score"] is None


def test_fpocket_does_not_misuse_solvent_probe_as_alpha_sphere_radius(monkeypatch):
    import app.tools.castp as m
    from types import SimpleNamespace
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="fpocket", stderr="", returncode=0)
    monkeypatch.setattr(m.subprocess, "run", run)
    m._run_fpocket_analysis("fpocket", _sample_pdb(), "TEST", 1.4)
    execution = next(args for args in calls if "-f" in args)
    assert "-r" not in execution


def test_native_descriptors_cannot_overwrite_scores_or_geometry(tmp_path):
    (tmp_path / "input_info.txt").write_text(
        "Pocket 1 :\nScore : 0.664\nDruggability Score : 0.855\n"
        "Number of Alpha Spheres : 143\nTotal SASA : 214.924\n"
        "Polar SASA : 111.068\nApolar SASA : 103.856\nVolume : 1455.507\n"
        "Mean alpha sphere radius : 3.977\nHydrophobicity score: 39.727\n"
        "Volume score: 3.939\nPolarity score: 13\nCharge score : -2\n"
        "Alpha sphere density: 8.233\n")
    pocket = _parse_fpocket(tmp_path, "TEST", 1.4)["pockets"][0]
    assert pocket["score"] == 0.664
    assert pocket["druggability_score"] == 0.855
    assert pocket["volume_sa"] == 1455.507
    assert pocket["area_sa"] == 214.924
    assert pocket["alpha_spheres"] == 143
    assert pocket["method_metrics"]["fpocket_total_sasa"] == 214.924


def test_fpocket_version_uses_ansi_stripped_banner(monkeypatch):
    from types import SimpleNamespace
    import app.tools.castp as m
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout="***** POCKET HUNTING BEGINS *****\n:||: \x1b[1mfpocket 4.0\x1b[0m :||:", stderr=""))
    assert m._fpocket_version("fpocket") == "4.0"
