"""Bound the entire NCBI fallback, including submit and fetch retries."""
import asyncio
import pytest
from app.integrations.ncbi import blast


@pytest.mark.asyncio
async def test_outer_deadline_returns_explicit_incomplete_search(monkeypatch):
    observed = []
    async def timeout(coroutine, timeout):
        observed.append(timeout)
        coroutine.close()
        raise asyncio.TimeoutError
    monkeypatch.setattr(blast.asyncio, "wait_for", timeout)
    result = await blast.run_blast_with_retry("ACDEFGHIKLMNPQ", max_wait_seconds=60)
    assert observed == [180]
    assert result["status"] == "TIMEOUT"
    assert result["search_complete"] is False
    assert "hard deadline" in result["error"]
    assert "hits" not in result


@pytest.mark.asyncio
async def test_outer_deadline_preserves_completed_provider_result(monkeypatch):
    expected = {"raw": "<BlastOutput/>", "rid": "test"}
    async def completed(*args, **kwargs):
        return expected
    monkeypatch.setattr(blast, "_run_blast_attempts", completed)
    assert await blast.run_blast_with_retry("ACDEFGHIKLMNPQ") == expected


@pytest.mark.asyncio
async def test_external_cancellation_is_not_reported_as_biological_result(monkeypatch):
    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError
    monkeypatch.setattr(blast, "_run_blast_attempts", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await blast.run_blast_with_retry("ACDEFGHIKLMNPQ")
