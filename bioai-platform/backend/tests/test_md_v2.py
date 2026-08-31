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
        assert s["expectation"]  # human explanation present for every stage


def test_analyze_runs_full_dag(client):
    payload = _payload(production_ps=20, nvt_ps=20)
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()

    assert body["requested"]["pdb_id"] == "TEST"
    assert body["requested"]["source"] == "provided-pdb-text"

    stages = body["pipeline"]["stages"]
    steps = [s["step"] for s in stages]
    assert len(steps) == 10
    assert body["pipeline"]["pipeline_status"] in ("PASS", "WARN")

    # NPT is not-applicable in implicit solvent -> WARN, not a hard STOP.
    npt = [s for s in stages if s["step"] == "md_npt"][0]
    assert npt["qc"]["status"] == "WARN"
    npt_data = npt["data"]
    assert npt_data["applicable"] is False

    # Trajectory QC produced the four structural observables.
    traj = [s for s in stages if s["step"] == "md_traj"][0]
    assert all(m["status"] == "PASS" for m in traj["qc"]["metrics"])

    # Final convergence stage has a readiness verdict.
    conv = [s for s in stages if s["step"] == "md_convergence"][0]
    assert "readiness" in conv["data"]


def test_analyze_default_nvt_with_production_ps(client):
    """Regression: 'production_ps' without 'nvt_ps' must not crash the engine
    (previously MdEngine init and NVT defaulted to None steps -> TypeError)."""
    payload = _payload(production_ps=20)  # no nvt_ps -> engine default NVT
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    stages = body["pipeline"]["stages"]
    assert len(stages) == 10
    nvt = [s for s in stages if s["step"] == "md_nvt"][0]
    assert nvt["qc"]["status"] == "PASS"
    assert body["pipeline"]["pipeline_status"] in ("PASS", "WARN")


def test_analyze_garbage_structure_stops_at_input(client):
    # Contains "ATOM" so the router's cheap pre-check passes; still unparseable,
    # so it must be caught by the md_input stage's own structure-QC gate.
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
    assert body["pipeline"]["stopped_at"] == "md_input"
    assert body["pipeline"]["stages"][0]["decision"] == "STOP"


def test_analyze_invalid_combo_stops_at_ff(client):
    payload = _payload(forcefield="bogus", solvent="obc2")
    r = client.post("/api/md/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    # FF resolution fails on the unknown key -> blocking FAIL at md_ff.
    assert body["pipeline"]["pipeline_status"] == "FAIL"
    assert body["pipeline"]["stopped_at"] == "md_ff"
    assert body["pipeline"]["stages"][1]["decision"] == "STOP"
