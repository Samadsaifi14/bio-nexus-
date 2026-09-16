"""Tests for the staged MD v2 router (in-process DAG + QC contracts)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import md_v2
from app.tools.md_config import _DIPEPTIDE_PDB


@pytest.fixture(scope="module")
def client():
    app = FastAPI(title="MD v2 Router Tests")
    app.include_router(md_v2.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _payload(**kw):
    base = {"pdb_id": "TEST", "pdb_text": _DIPEPTIDE_PDB}
    base.update(kw)
    return base


def test_engine_status_reports_openmm_primary(client):
    r = client.get("/api/md/v2/engine")
    assert r.status_code == 200
    body = r.json()
    assert body["primary"] == "openmm"
    assert "openmm" in body["engines"]
    assert "gromacs" in body["engines"]


def test_stages_lists_contracts(client):
    r = client.get("/api/md/v2/stages")
    assert r.status_code == 200
    body = r.json()
    steps = [s["step"] for s in body["stages"]]
    assert steps[0] == "md_input"
    assert steps[-1] == "md_convergence"
    assert len(steps) == 10
    for s in body["stages"]:
        assert s["expectation"]


def test_analyze_runs_full_dag(client):
    payload = _payload(production_ps=20, nvt_ps=20)
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()

    assert body["requested"]["pdb_id"] == "TEST"
    assert body["requested"]["source"] == "provided-pdb-text"
    assert body["method"] == "Short implicit-solvent OpenMM MD"
    assert body["engine"] == "OpenMM"
    assert body["status"] in ("VALID", "DEGRADED")
    assert len(body["input_sha256"]) == 64
    assert len(body["output_sha256"]) == 64

    stages = body["pipeline"]["stages"]
    steps = [s["step"] for s in stages]
    assert len(steps) == 10
    assert body["pipeline"]["pipeline_status"] in ("PASS", "WARN")

    # NPT is not-applicable in implicit solvent -> WARN, not a hard STOP.
    npt = [s for s in stages if s["step"] == "md_npt"][0]
    assert npt["qc"]["status"] == "WARN"
    npt_data = npt["data"]
    assert npt_data["applicable"] is False

    # Production retains exact engine-emitted per-frame arrays for rendering.
    production = [s for s in stages if s["step"] == "md_production"][0]
    assert production["data"]["potential_energy"]
    assert production["data"]["temperature"]
    assert production["data"]["radius_of_gyration"]
    assert len(production["data"]["potential_energy"]) == production["data"]["n_frames"]
    assert len(production["data"]["radius_of_gyration"]) == production["data"]["n_frames"]

    # Trajectory QC produced the four structural observables.
    traj = [s for s in stages if s["step"] == "md_traj"][0]
    assert all(m["status"] == "PASS" for m in traj["qc"]["metrics"])
    assert traj["data"]["rmsd"]
    assert traj["data"]["rmsf"]
    assert traj["data"]["sasa"]

    # Plot descriptors must point to retained scientific arrays; no placeholder
    # zero-valued plot is manufactured when a series is absent.
    plot_ids = {plot["id"] for plot in body["plots"]}
    assert "temperature-vs-step" in plot_ids
    assert "potential-energy-vs-step" in plot_ids
    assert "rmsd-vs-frame" in plot_ids
    assert "rmsf-vs-residue" in plot_ids
    assert "radius-of-gyration-vs-step" in plot_ids
    assert "sasa-vs-step" in plot_ids
    for plot in body["plots"]:
        assert plot["data"]
        assert all(plot["y_key"] in row and row[plot["y_key"]] is not None for row in plot["data"])

    assert body["validation"]["real_trajectory_emitted"] is True
    assert body["validation"]["trajectory_qc_emitted"] is True
    assert body["validation"]["stage_errors"] == []

    conv = [s for s in stages if s["step"] == "md_convergence"][0]
    assert "readiness" in conv["data"]


def test_analyze_default_nvt_with_production_ps(client):
    """Regression: 'production_ps' without 'nvt_ps' must not crash the engine."""
    payload = _payload(production_ps=20)
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    stages = body["pipeline"]["stages"]
    assert len(stages) == 10
    nvt = [s for s in stages if s["step"] == "md_nvt"][0]
    assert nvt["qc"]["status"] in ("PASS", "WARN")
    assert nvt["qc"]["status"] != "FAIL"
    assert body["pipeline"]["pipeline_status"] in ("PASS", "WARN")


def test_analyze_garbage_structure_stops_at_input(client):
    payload = _payload(
        pdb_text="HEADER    BROKEN\nTITLE     not a real structure\n"
                 "ATOM      1  N   MET A   1    1.0   1.0   1.0  1.0 99.99\n"
                 "not a coordinate line at all\nEND\n",
        pdb_id="BAD1",
    )
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline"]["pipeline_status"] == "FAIL"
    assert body["status"] == "FAILED"
    assert body["pipeline"]["stopped_at"] == "md_input"
    assert body["pipeline"]["stages"][0]["decision"] == "STOP"
    assert body["validation"]["stage_errors"]
    assert body["plots"] == []


def test_analyze_invalid_combo_stops_at_ff(client):
    payload = _payload(forcefield="bogus", solvent="obc2")
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline"]["pipeline_status"] == "FAIL"
    assert body["status"] == "FAILED"
    assert body["pipeline"]["stopped_at"] == "md_ff"
    assert body["pipeline"]["stages"][1]["decision"] == "STOP"
    assert any(item["stage"] == "md_ff" for item in body["validation"]["stage_errors"])
