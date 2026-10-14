import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.rnaseq import durable
from app.routers import geo_search, pipeline_v2


def test_only_complete_valid_engine_events_are_visible(tmp_path):
    path = tmp_path / "progress.jsonl"
    path.write_bytes(b'{"step":1,"status":"complete"}\ninvalid\n{"step":11,"status":"complete"}\n{"step":true,"status":"running"}\n{"step":2,"status":"running"}\n{"step":3')
    assert durable.read_progress(path) == [{"step": 1, "status": "complete"}, {"step": 2, "status": "running"}]
    assert durable.read_progress(tmp_path / "missing") == []


def test_current_attempt_and_owner_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("BIONEXUS_EXPRESSION_ROOT", str(tmp_path / "queue"))
    monkeypatch.setattr(durable, "readiness", lambda *args: {"available": True, "missing": []})
    counts = tmp_path / "counts.tsv"; counts.write_text("gene\ts1\ng1\t1\n")
    meta = tmp_path / "metadata.tsv"; meta.write_text("sample\tcondition\ns1\thealthy\n")
    job_id = durable.enqueue("alice", counts, meta, durable.ExpressionParameters(), {}, full_analysis=True)["job_id"]
    job = durable.claim("worker")
    folder = durable.root() / job_id
    (folder / "progress_0.jsonl").write_text('{"step":10,"status":"complete"}\n')
    (folder / "progress_1.jsonl").write_text('{"step":1,"status":"running"}\n')
    assert durable.status(job_id, "alice")["progress"] == [{"step": 1, "status": "running"}]
    with pytest.raises(FileNotFoundError):
        durable.status(job_id, "bob")


def test_live_submission_never_silently_uses_blocking_fallback(monkeypatch):
    monkeypatch.setattr(durable, "readiness", lambda: {"available": False, "missing": ["worker heartbeat"]})
    async def forbidden(*args):
        raise AssertionError("No study download or direct execution without a live worker")
    monkeypatch.setattr(geo_search, "_prepare_automatic", forbidden)
    with pytest.raises(HTTPException) as error:
        asyncio.run(geo_search.run_geo_analysis(geo_search.AutomaticSelection(accession="GSE336901", require_durable=True), "alice"))
    assert error.value.status_code == 503
    assert "worker heartbeat" in error.value.detail


def test_blast_preview_preserves_submission_without_terminal_status(monkeypatch):
    calls = []
    class Table:
        def select(self, fields): return self
        def eq(self, key, value):
            calls.append((key, value)); return self
        def execute(self): return SimpleNamespace(data=[{"user_id": "alice", "context_json": {"database": "nr", "input_sha256": "input", "collection_id": "batch"}}])
        def update(self, payload): calls.append(payload); return self
    monkeypatch.setattr(pipeline_v2, "get_supabase", lambda: SimpleNamespace(table=lambda name: Table()))
    pipeline_v2._persist_blast_preview("11111111-1111-4111-8111-111111111111", {"blast": {"hits": [], "count": 0, "search_complete": True}})
    payload = next(item for item in calls if isinstance(item, dict))
    assert set(payload) == {"context_json"}
    assert payload["context_json"]["database"] == "nr"
    assert payload["context_json"]["collection_id"] == "batch"
    assert payload["context_json"]["blast"]["search_complete"] is True
    assert ("user_id", "alice") in calls
