"""
Smoke tests for the Function Prediction endpoints.

Covers:
- POST /api/function/predict creates a job (auth required)
- GET /api/function/status/{job_id} returns status (auth required)
- Invalid PDB ID returns 422
- Missing auth returns 401
"""

import pytest

BASE_PREDICT = "/api/function/predict"
BASE_STATUS = "/api/function/status"


class TestFunctionAuth:
    """Verify auth enforcement."""

    def test_no_auth_returns_401(self, client):
        resp = client.post(BASE_PREDICT, json={"pdb_id": "1crn"})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.post(
            BASE_PREDICT,
            json={"pdb_id": "1crn"},
            headers={"Authorization": "Bearer bad.token.here"},
        )
        assert resp.status_code == 401


class TestFunctionPredict:
    """POST /api/function/predict validation."""

    def test_valid_request_returns_job(self, client, auth_headers):
        resp = client.post(BASE_PREDICT, json={"pdb_id": "1crn"}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] in ("queued", "submitted", "running")

    def test_invalid_pdb_id_too_short(self, client, auth_headers):
        resp = client.post(BASE_PREDICT, json={"pdb_id": "1cr"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_invalid_pdb_id_special_chars(self, client, auth_headers):
        resp = client.post(BASE_PREDICT, json={"pdb_id": "X!Y@"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_missing_pdb_id_returns_422(self, client, auth_headers):
        resp = client.post(BASE_PREDICT, json={}, headers=auth_headers)
        assert resp.status_code == 422


class TestFunctionStatus:
    """GET /api/function/status/{job_id} validation."""

    def test_no_auth_returns_401(self, client):
        resp = client.get(f"{BASE_STATUS}/fake-id")
        assert resp.status_code == 401

    def test_nonexistent_job_returns_error(self, client, auth_headers):
        resp = client.get(f"{BASE_STATUS}/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert resp.status_code in (404, 422, 500)
