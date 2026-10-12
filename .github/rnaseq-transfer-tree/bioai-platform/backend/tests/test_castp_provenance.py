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



async def test_sasa_fallback_is_degraded_and_attributed(monkeypatch):
    import app.tools.castp as m

    monkeypatch.setattr(m, "FPOCKET_BIN", "C:/fake/fpocket.exe")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    loop = _ExecLoop()
    monkeypatch.setattr(m.asyncio, "get_running_loop", lambda: loop)

    result = await m._analyze_pockets(_sample_pdb(), "TEST", 1.4)
    assert result["method"] == "sasa_heuristic"
    assert result["fallback_used"] is True
    assert result["pockets"] == []
    tried = {t["method"]: t["status"] for t in result["methods_tried"]}
    assert tried["fpocket"] == "unavailable"
    assert tried["sasa_heuristic"] == "ran_no_pockets"
    assert "CASTp" in result["note"] and "fpocket" in result["note"]



async def test_total_failure_returns_failed(monkeypatch):
    import app.tools.castp as m

    class _BrokenLoop:
        async def run_in_executor(self, _pool, _fn, *_args):
            raise RuntimeError("SASA engine crashed")

    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(
        m.asyncio, "get_running_loop",
        lambda: _BrokenLoop(),
    )

    result = await m._analyze_pockets(_sample_pdb(), "TEST", 1.4)
    assert result["status"] == "FAILED"
    assert result["pockets"] == []
    assert result["method"] == "none"
    assert result["fallback_used"] is True
    assert "SASA engine crashed" in result["error"]
    assert result["methods_tried"][0] == {"method": "fpocket", "status": "unavailable"}


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
