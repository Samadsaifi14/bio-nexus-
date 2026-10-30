"""Tests for the shared analysis-job registry.

The registry mirrors every tool run into the Supabase ``jobs`` table that the
Jobs and History pages read. Writes are queued on a single worker thread, so each
test drains that worker before asserting. A regression here previously surfaced
as a ``TypeError`` inside tool routers (every ``start``/``record_completed`` call
passed keyword arguments).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import job_registry


class FakeQuery:
    def __init__(self, rows: dict[str, dict], payload: dict | None = None, mode: str = "select"):
        self.rows = rows
        self.payload = payload
        self.mode = mode
        self._id: str | None = None

    def insert(self, payload: dict):
        return FakeQuery(self.rows, payload, "insert")

    def update(self, payload: dict):
        return FakeQuery(self.rows, payload, "update")

    def select(self, *_columns):
        return self

    def eq(self, column: str, value: str):
        if column == "id":
            self._id = value
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        if self.mode == "insert":
            self.rows[self.payload["id"]] = dict(self.payload)
            return SimpleNamespace(data=[self.payload])
        if self.mode == "update":
            assert self._id in self.rows, f"update for unknown row {self._id}"
            self.rows[self._id].update(self.payload)
            return SimpleNamespace(data=[self.rows[self._id]])
        row = self.rows.get(self._id or "")
        return SimpleNamespace(data=[row] if row else [])


class FakeClient:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def table(self, _name: str) -> FakeQuery:
        return FakeQuery(self.rows)


@pytest.fixture()
def registry(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(job_registry, "_client", lambda: client)
    yield client
    # Drain the writer thread so queued writes cannot leak into the next test.
    job_registry._pool.submit(lambda: None).result(timeout=5)


def test_start_accepts_keyword_arguments(registry):
    job_id = job_registry.start(
        "docking",
        "user-1",
        query_preview="EGFR · erlotinib",
        context={"ligand": "erlotinib"},
    )
    job_registry._pool.submit(lambda: None).result(timeout=5)

    assert job_id is not None
    row = registry.rows[job_id]
    assert row["tool"] == "docking"
    assert row["status"] == "running"
    assert row["query_preview"] == "EGFR · erlotinib"
    assert row["context_json"]["ligand"] == "erlotinib"


def test_finish_moves_row_to_complete(registry):
    job_id = job_registry.start("phylo", "user-1")
    job_registry.finish(job_id, status="complete", context={"tree_preview": "(A,B);"})
    job_registry._pool.submit(lambda: None).result(timeout=5)

    row = registry.rows[job_id]
    assert row["status"] == "complete"
    assert row["progress_pct"] == 100
    assert row["completed_at"] is not None
    assert row["context_json"]["tree_preview"] == "(A,B);"


def test_record_completed_writes_one_finished_row(registry):
    job_registry.record_completed(
        "admet",
        "user-1",
        query_preview="aspirin",
        context={"mw": 180.16},
    )
    job_registry._pool.submit(lambda: None).result(timeout=5)

    assert len(registry.rows) == 1
    row = next(iter(registry.rows.values()))
    assert row["tool"] == "admet"
    assert row["status"] == "complete"
    assert row["context_json"]["mw"] == 180.16


def test_propagate_patch_records_failure(registry):
    job_id = job_registry.start("md_v2", "user-1")
    job_registry.propagate_patch("md_v2", job_id, {"status": "failed", "error": "boom"})
    job_registry._pool.submit(lambda: None).result(timeout=5)

    row = registry.rows[job_id]
    assert row["status"] == "failed"
    assert row["error"] == "boom"


def test_anonymous_runs_are_not_recorded(registry):
    assert job_registry.start("docking", None) is None
    job_registry.record_completed("admet", None)
    job_registry._pool.submit(lambda: None).result(timeout=5)

    assert registry.rows == {}
