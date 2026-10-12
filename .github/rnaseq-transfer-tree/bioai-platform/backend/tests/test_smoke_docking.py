"""
Smoke tests for the Docking endpoints.

Covers:
- POST /api/docking/run creates a job (auth required)
- GET /api/docking/status/{job_id} returns status (auth required)
- GET /api/docking lists jobs (auth required)
- Missing auth returns 401
- Invalid request body returns 422
"""

import pytest

BASE_RUN = "/api/docking/run"
BASE_STATUS = "/api/docking/status"
BASE_LIST = "/api/docking"


class TestDockingAuth:
    """Verify auth enforcement on all docking endpoints."""

    def test_run_no_auth_returns_401(self, client):
        resp = client.post(BASE_RUN, json={"smiles": "CC(=O)O"})
        assert resp.status_code == 401

    def test_list_no_auth_returns_401(self, client):
        resp = client.get(BASE_LIST)
        assert resp.status_code == 401

    def test_status_no_auth_returns_401(self, client):
        resp = client.get(f"{BASE_STATUS}/fake-id")
        assert resp.status_code == 401


class TestDockingRun:
    """POST /api/docking/run validation."""

    def test_valid_request_returns_job(self, client, auth_headers):
        resp = client.post(
            BASE_RUN,
            json={"smiles": "CC(=O)O", "pdb_id": "", "grid_size": [20.0, 20.0, 20.0]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] in ("queued", "submitted", "running")

    def test_missing_smiles_returns_422(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_empty_smiles_accepted(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"smiles": ""}, headers=auth_headers)
        # Backend accepts empty smiles and queues a job (worker may fail it later)
        assert resp.status_code == 200
        assert "job_id" in resp.json()

    def test_custom_grid_params_accepted(self, client, auth_headers):
        resp = client.post(
            BASE_RUN,
            json={
                "smiles": "CC(=O)O",
                "grid_size": [10.0, 10.0, 10.0],
                "exhaustiveness": 4,
                "num_modes": 3,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestDockingStatus:
    """GET /api/docking/status/{job_id} validation."""

    def test_nonexistent_job_returns_error(self, client, auth_headers):
        resp = client.get(f"{BASE_STATUS}/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert resp.status_code in (404, 422, 500)


class TestDockingList:
    """GET /api/docking list endpoint."""

    def test_list_returns_dict(self, client, auth_headers):
        resp = client.get(BASE_LIST, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs" in body
        assert isinstance(body["jobs"], list)
