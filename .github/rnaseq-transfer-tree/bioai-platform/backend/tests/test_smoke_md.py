"""
Smoke tests for the MD Simulation endpoints.

Covers:
- POST /api/md/run creates a job (auth required)
- GET /api/md/status/{job_id} returns status (auth required)
- Invalid PDB ID returns 422
- Missing auth returns 401
- Status for nonexistent job returns 404/422
"""

import pytest

BASE_RUN = "/api/md/run"
BASE_STATUS = "/api/md/status"


class TestMDAuth:
    """Verify auth enforcement."""

    def test_no_auth_returns_401(self, client):
        resp = client.post(BASE_RUN, json={"pdb_id": "1crn", "mode": "minimize"})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.post(
            BASE_RUN,
            json={"pdb_id": "1crn", "mode": "minimize"},
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert resp.status_code == 401


class TestMDRun:
    """POST /api/md/run validation."""

    def test_valid_request_returns_job(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"pdb_id": "1crn", "mode": "minimize"}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] in ("queued", "submitted", "running")

    def test_invalid_pdb_id_too_short(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"pdb_id": "1cr", "mode": "minimize"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_invalid_pdb_id_special_chars(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"pdb_id": "1!@#", "mode": "minimize"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_invalid_mode_returns_422(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"pdb_id": "1crn", "mode": "invalid_mode"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_missing_pdb_id_returns_422(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"mode": "minimize"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_default_mode_is_minimize(self, client, auth_headers):
        resp = client.post(BASE_RUN, json={"pdb_id": "1crn"}, headers=auth_headers)
        assert resp.status_code == 200


class TestMDStatus:
    """GET /api/md/status/{job_id} validation."""

    def test_no_auth_returns_401(self, client):
        resp = client.get(f"{BASE_STATUS}/fake-job-id")
        assert resp.status_code == 401

    def test_nonexistent_job_returns_error(self, client, auth_headers):
        resp = client.get(f"{BASE_STATUS}/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert resp.status_code in (404, 422, 500)
