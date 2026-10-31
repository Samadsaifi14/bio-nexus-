"""Stale-job reconciliation.

Live evidence: `jobs` row 500a381e-... (a docking mirror) and 25 June/July
pipeline rows were non-terminal with no live owner. The old sweep only matched
`claimed_at < cutoff`, so rows whose owner died before/without a claim
(`claimed_at IS NULL`) were never reconciled and stayed "running" forever on
Jobs/History.

The sweep must also never requeue a tool-registry mirror as a pipeline job, and
must not silently re-run months-old analyses.
"""

from __future__ import annotations

import httpx
import pytest

import app.worker as worker
from app.services import job_registry


@pytest.fixture(autouse=True)
def _no_registry_writes(monkeypatch):
    monkeypatch.setattr(job_registry, "propagate_patch", lambda *a, **k: None)
    monkeypatch.setattr(worker.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(worker.settings, "SUPABASE_SERVICE_ROLE_KEY", "test-key")


class _Resp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = f"fake {status_code}"

    def json(self):
        return self._payload


def _iso_minutes_ago(minutes: float) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _install(monkeypatch, claimed_rows, unclaimed_rows):
    """Fake the two sweep GETs and capture PATCHes."""
    patches: list[tuple[str, dict]] = []

    def fake_get(url, headers, timeout=None):
        if "claimed_at=is.null" in url:
            return _Resp(200, unclaimed_rows)
        return _Resp(200, claimed_rows)

    def fake_patch(url, headers, json, timeout=None):
        patches.append((url, json))
        return _Resp(200, [{"id": "x", **json}])

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "patch", fake_patch)
    return patches


class TestSweepStuck:
    def test_unclaimed_mirror_row_is_closed_not_requeued(self, monkeypatch):
        # The live docking mirror: status running, claimed_at NULL, attempts 0.
        rows = [{
            "id": "500a381e",
            "status": "running",
            "attempts": 0,
            "max_attempts": 3,
            "claimed_at": None,
            "created_at": _iso_minutes_ago(20 * 60),
            "tool": "docking",
        }]
        patches = _install(monkeypatch, [], rows)

        count = worker._sweep_stuck("jobs")

        assert count == 1
        url, body = patches[0]
        assert "id=eq.500a381e" in url
        assert body["status"] == "failed", "a tool mirror must never be requeued"
        assert body["completed_at"]
        assert "Interrupted" in body["error"]

    def test_old_pipeline_claim_is_failed_not_rerun(self, monkeypatch):
        rows = [{
            "id": "b38b1696",
            "status": "running",
            "attempts": 1,
            "max_attempts": 3,
            "claimed_at": _iso_minutes_ago(60 * 24 * 30),
            "created_at": _iso_minutes_ago(60 * 24 * 60),
            "tool": "pipeline",
        }]
        patches = _install(monkeypatch, rows, [])

        assert worker._sweep_stuck("jobs") == 1
        _, body = patches[0]
        assert body["status"] == "failed"
        assert body["completed_at"]
        assert "Interrupted" in body["error"]

    def test_recent_stale_pipeline_claim_is_requeued(self, monkeypatch):
        rows = [{
            "id": "recent",
            "status": "running",
            "attempts": 1,
            "max_attempts": 3,
            "claimed_at": _iso_minutes_ago(2 * 60),
            "created_at": _iso_minutes_ago(2 * 60 + 5),
            "tool": "pipeline",
        }]
        patches = _install(monkeypatch, rows, [])

        assert worker._sweep_stuck("jobs") == 1
        _, body = patches[0]
        assert body["status"] == "queued"
        assert body["claimed_at"] is None
        assert "retrying" in body["error"]

    def test_fresh_unclaimed_rows_are_untouched(self, monkeypatch):
        rows = [{
            "id": "fresh-wizard",
            "status": "running",
            "attempts": 0,
            "max_attempts": 3,
            "claimed_at": None,
            "created_at": _iso_minutes_ago(10),
            "tool": "wizard_v2",
        }]
        patches = _install(monkeypatch, [], rows)

        assert worker._sweep_stuck("jobs") == 0
        assert patches == []

    def test_old_unclaimed_pipeline_row_is_requeued_within_retry_budget(self, monkeypatch):
        # Never claimed because the process died right after insert: retry it
        # (still recent enough that re-running is meaningful).
        rows = [{
            "id": "orphan-insert",
            "status": "running",
            "attempts": 0,
            "max_attempts": 3,
            "claimed_at": None,
            "created_at": _iso_minutes_ago(2 * 60),
            "tool": "pipeline",
        }]
        patches = _install(monkeypatch, [], rows)

        assert worker._sweep_stuck("jobs") == 1
        _, body = patches[0]
        assert body["status"] == "queued"

    def test_stale_claim_on_tool_table_is_requeued(self, monkeypatch):
        rows = [{
            "id": "dock-1",
            "status": "running",
            "attempts": 1,
            "max_attempts": 3,
            "claimed_at": _iso_minutes_ago(2 * 60),
            "created_at": _iso_minutes_ago(2 * 60 + 5),
        }]
        patches = _install(monkeypatch, rows, [])

        assert worker._sweep_stuck("docking_jobs") == 1
        url, body = patches[0]
        assert "docking_jobs?id=eq.dock-1" in url
        assert body["status"] == "queued"
        assert "done_at" not in body

    def test_query_failure_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(400, {"message": "bad"}))
        monkeypatch.setattr(
            httpx, "patch", lambda *a, **k: pytest.fail("patch should not fire")
        )
        assert worker._sweep_stuck("jobs") == 0


class TestClaimScope:
    def test_pipeline_claim_rpc_filters_tool(self):
        sql = worker._claim_rcp_sql("jobs")
        assert "AND tool = 'pipeline'" in sql

    def test_tool_table_claim_rpc_not_filtered(self):
        assert "tool = 'pipeline'" not in worker._claim_rcp_sql("docking_jobs")

    def test_direct_claim_url_filters_pipeline_tools(self, monkeypatch):
        seen = []

        def fake_get(url, headers, timeout=None):
            seen.append(url)
            return _Resp(200, [])

        monkeypatch.setattr(httpx, "get", fake_get)
        worker._claim_direct("jobs", worker.WORKER_ID)

        assert seen and "tool=eq.pipeline" in seen[0]
