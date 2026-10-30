"""Regression tests for MD v2 hosted synchronous execution limits."""

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import md_v2
from app.tools.md_config import _DIPEPTIDE_PDB


def _client():
    app = FastAPI()
    app.include_router(md_v2.router)
    return TestClient(app, raise_server_exceptions=False)


def test_large_explicit_production_request_is_capped(monkeypatch):
    observed = {}

    class FakePipe:
        def run(self, sample):
            observed.update(sample)
            return {
                "pipeline": "md-v2-test",
                "pipeline_status": "WARN",
                "pipeline_decision": "CONTINUE",
                "stopped_at": None,
                "stages": [],
                "warnings": [],
            }

    monkeypatch.setattr(md_v2, "build_md_pipeline", lambda: FakePipe())

    with _client() as client:
        response = client.post(
            "/api/md/v2/analyze",
            json={"pdb_id": "TEST", "pdb_text": _DIPEPTIDE_PDB, "production_ps": 250},
        )

    assert response.status_code == 200
    body = response.json()
    assert observed["production_steps"] == 10_000  # 20 ps at a 2 fs timestep
    assert body["requested"]["production_ps"] == 250
    assert body["requested"]["effective_production_ps"] == 20
    assert body["requested"]["production_capped"] is True
    assert body["requested"]["synchronous_limit_ps"] == 20
    assert any("capped to 20 ps" in warning for warning in body["pipeline"]["warnings"])


def test_pipeline_exception_returns_structured_503(monkeypatch):
    class BrokenPipe:
        def run(self, sample):
            raise RuntimeError("OpenMM platform unavailable")

    monkeypatch.setattr(md_v2, "build_md_pipeline", lambda: BrokenPipe())

    with _client() as client:
        response = client.post(
            "/api/md/v2/analyze",
            json={"pdb_id": "TEST", "pdb_text": _DIPEPTIDE_PDB, "production_ps": 20},
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "MD engine failed before producing a scientific result" in detail
    assert "OpenMM platform unavailable" in detail


def test_background_job_returns_id_and_can_be_polled(monkeypatch):
    class FakePipe:
        def run(self, sample):
            return {
                "pipeline": "md-v2-test",
                "pipeline_status": "PASS",
                "pipeline_decision": "CONTINUE",
                "stopped_at": None,
                "stages": [],
                "warnings": [],
            }

    monkeypatch.setattr(md_v2, "build_md_pipeline", lambda: FakePipe())

    with _client() as client:
        submitted = client.post(
            "/api/md/v2/jobs",
            json={"pdb_id": "TEST", "pdb_text": _DIPEPTIDE_PDB, "production_ps": 5},
        )
        assert submitted.status_code == 200
        job_id = submitted.json()["job_id"]
        assert submitted.json()["status"] == "queued"

        snapshot = None
        for _ in range(100):
            polled = client.get(f"/api/md/v2/jobs/{job_id}")
            assert polled.status_code == 200
            snapshot = polled.json()
            if snapshot["status"] in ("complete", "failed"):
                break
            time.sleep(0.05)

    assert snapshot is not None
    assert snapshot["status"] == "complete", snapshot
    assert snapshot["result"]["pipeline"]["pipeline_status"] == "PASS"


def test_background_job_reports_pipeline_failure(monkeypatch):
    class BrokenPipe:
        def run(self, sample):
            raise RuntimeError("OpenMM platform unavailable")

    monkeypatch.setattr(md_v2, "build_md_pipeline", lambda: BrokenPipe())

    with _client() as client:
        submitted = client.post(
            "/api/md/v2/jobs",
            json={"pdb_id": "TEST", "pdb_text": _DIPEPTIDE_PDB, "production_ps": 5},
        )
        job_id = submitted.json()["job_id"]

        snapshot = None
        for _ in range(100):
            snapshot = client.get(f"/api/md/v2/jobs/{job_id}").json()
            if snapshot["status"] in ("complete", "failed"):
                break
            time.sleep(0.05)

    assert snapshot is not None
    assert snapshot["status"] == "failed"
    assert "OpenMM platform unavailable" in (snapshot["error"] or "")
