"""
Deterministic tests for the durable worker's direct-claim fallback (no network).

The `jobs` table has no `updated_at` column (migration 005 adds it only to
docking_jobs/sequencing_jobs), so the fallback PATCH must omit it there —
sending it would make PostgREST 400 and silently strand queued pipeline jobs.
"""

import httpx

import app.worker as worker
from app.worker import WORKER_ID


def _fake_response(status_code: int, payload):
    class _Resp:
        def __init__(self):
            self.status_code = status_code
            self._payload = payload
            self.text = f"fake {status_code}"

        def json(self):
            return self._payload

    return _Resp()


def _patch_settings(monkeypatch):
    monkeypatch.setattr(worker.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(worker.settings, "SUPABASE_SERVICE_ROLE_KEY", "test-key")


def _track(request_log):
    def _fake_get(url, headers, timeout=None):
        request_log["gets"].append(url)
        if "status=eq.queued" in url:
            return _fake_response(200, [{"id": "job-1", "attempts": 2, "max_attempts": 3}])
        return _fake_response(200, [])

    def _fake_patch(url, headers, json, timeout=None):
        request_log["patches"].append((url, json))
        return _fake_response(200, [{**json, "id": "job-1"}])

    return _fake_get, _fake_patch


class TestClaimDirect:
    def test_claim_pipeline_job_omits_updated_at(self, monkeypatch):
        _patch_settings(monkeypatch)
        request_log = {"gets": [], "patches": []}
        fake_get, fake_patch = _track(request_log)
        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "patch", fake_patch)

        job = worker._claim_direct("jobs", WORKER_ID)

        assert job is not None
        assert job["id"] == "job-1"
        url, body = request_log["patches"][0]
        assert url.startswith("https://example.supabase.co/rest/v1/jobs?id=eq.job-1")
        assert body["status"] == "running"
        assert body["claimed_by"] == WORKER_ID
        assert body["attempts"] == 3
        assert "updated_at" not in body, "jobs table has no updated_at column"

    def test_claim_docking_job_keeps_updated_at(self, monkeypatch):
        _patch_settings(monkeypatch)
        request_log = {"gets": [], "patches": []}
        fake_get, fake_patch = _track(request_log)
        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "patch", fake_patch)

        job = worker._claim_direct("docking_jobs", WORKER_ID)

        assert job is not None
        url, body = request_log["patches"][0]
        assert url.startswith("https://example.supabase.co/rest/v1/docking_jobs?id=eq.job-1")
        assert body["status"] == "running"
        assert "updated_at" in body

    def test_claim_falls_back_to_id_order_without_created_at(self, monkeypatch):
        _patch_settings(monkeypatch)
        request_log = {"gets": [], "patches": []}
        fake_get, fake_patch = _track(request_log)
        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "patch", fake_patch)

        worker._claim_direct("jobs", WORKER_ID)

        assert request_log["gets"][0].endswith("status=eq.queued&order=id.asc&limit=5&select=*")

    def test_skips_exhausted_attempts_client_side(self, monkeypatch):
        _patch_settings(monkeypatch)
        request_log = {"gets": [], "patches": []}

        def _fake_get(url, headers, timeout=None):
            request_log["gets"].append(url)
            return _fake_response(200, [
                {"id": "job-exhausted", "attempts": 3, "max_attempts": 3},
                {"id": "job-ok", "attempts": 0, "max_attempts": 3},
            ])

        def _fake_patch(url, headers, json, timeout=None):
            request_log["patches"].append((url, json))
            return _fake_response(200, [{**json, "id": "job-ok"}])

        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setattr(httpx, "patch", _fake_patch)

        job = worker._claim_direct("jobs", WORKER_ID)

        assert job["id"] == "job-ok"
        assert len(request_log["patches"]) == 1
        assert request_log["patches"][0][0].startswith("https://example.supabase.co/rest/v1/jobs?id=eq.job-ok")

    def test_no_queued_job_returns_none(self, monkeypatch):
        _patch_settings(monkeypatch)
        request_log = {"gets": [], "patches": []}

        def _no_rows(url, headers, timeout=None):
            request_log["gets"].append(url)
            return _fake_response(200, [])

        def _unused(url, headers, json, timeout=None):
            raise AssertionError("patch should not fire")

        monkeypatch.setattr(httpx, "get", _no_rows)
        monkeypatch.setattr(httpx, "patch", _unused)

        assert worker._claim_direct("jobs", WORKER_ID) is None

    def test_query_failure_returns_none(self, monkeypatch):
        _patch_settings(monkeypatch)
        request_log = {"gets": [], "patches": []}

        def _fail(url, headers, timeout=None):
            request_log["gets"].append(url)
            return _fake_response(500, {"detail": "boom"})

        def _unused(url, headers, json, timeout=None):
            raise AssertionError("patch should not fire")

        monkeypatch.setattr(httpx, "get", _fail)
        monkeypatch.setattr(httpx, "patch", _unused)

        assert worker._claim_direct("jobs", WORKER_ID) is None