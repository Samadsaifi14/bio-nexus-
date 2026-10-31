"""Foldseek comparison runs as a background job.

The synchronous endpoint polled Foldseek for up to ~120 s on the request path,
which the platform proxy turns into 502/504 on the Hugging Face deployment. The
job variant must record its terminal state on the shared row so Jobs/History and
the polling client agree.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers import structure_analysis as sa


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(sa.job_state, "mirror", lambda *a, **k: None)
    monkeypatch.setattr(sa.job_registry, "propagate_patch", lambda *a, **k: None)
    sa._jobs.clear()
    yield
    sa._jobs.clear()


@pytest.mark.asyncio
async def test_comparison_records_result_and_completes(monkeypatch):
    calls: dict = {}

    async def fake_search(pdb_id, chain, max_results):
        calls.update(pdb_id=pdb_id, chain=chain, max_results=max_results)
        return {
            "pdb_id": pdb_id,
            "chain": chain,
            "matches": [{"pdb_id": "2XYZ", "chain": "A", "tm_score": 0.91}],
            "method": "Foldseek TM-align",
            "database": "PDB100",
        }

    finished: dict = {}
    monkeypatch.setattr(sa, "_foldseek_search", fake_search)
    monkeypatch.setattr(
        sa.job_registry, "finish", lambda job_id, **kw: finished.update(job_id=job_id, **kw)
    )

    await sa._run_compare_job("cmp-1", "1ABC", "B", 7)

    assert calls == {"pdb_id": "1ABC", "chain": "B", "max_results": 7}
    job = sa._jobs["cmp-1"]
    assert job["status"] == "complete"
    assert job["result"]["matches"][0]["pdb_id"] == "2XYZ"
    assert finished["status"] == "complete"
    assert finished["context"]["match_count"] == 1


@pytest.mark.asyncio
async def test_comparison_failure_is_terminal_and_reported(monkeypatch):
    async def missing(*_a, **_k):
        raise HTTPException(404, "PDB file not found: 9ZZZ")

    finished: dict = {}
    monkeypatch.setattr(sa, "_foldseek_search", missing)
    monkeypatch.setattr(
        sa.job_registry, "finish", lambda job_id, **kw: finished.update(job_id=job_id, **kw)
    )

    await sa._run_compare_job("cmp-2", "9ZZZ", "A", 10)

    job = sa._jobs["cmp-2"]
    assert job["status"] == "failed"
    assert "PDB file not found" in job["error"]
    assert finished["status"] == "failed"
    assert "PDB file not found" in finished["error"]
