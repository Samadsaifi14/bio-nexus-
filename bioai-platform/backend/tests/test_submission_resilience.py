"""Submission and reconciliation must not lose a job to a transport failure.

Live evidence (2026-11-01, revision 68a5b64):

* ``POST /api/function/predict`` returned 502 for request ``cSRdnE`` while the
  ``docking_jobs`` row had in fact been inserted and a worker was running it.
  The Supabase insert response was lost after commit, and the router treated
  that as a failed submit.
* The stuck-job sweep failed every query with Postgres 22007 because the
  cutoff's ``+00:00`` arrived as a space (``+`` is a space in a query string),
  so no stale row could ever be failed or retried.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from app import worker
from app.routers import function_predict as fn


class _FakeTable:
    def __init__(self, db: "_FakeSupabase"):
        self.db = db
        self._op = None
        self._row: dict | None = None
        self._filters: list[tuple[str, object]] = []

    def insert(self, row: dict):
        self._op = "insert"
        self._row = row
        return self

    def select(self, *_args, **_kwargs):
        self._op = "select"
        return self

    def eq(self, key: str, value: object):
        self._filters.append((key, value))
        return self

    def limit(self, _count: int):
        return self

    def execute(self):
        if self._op == "insert":
            # Commit first, then lose the response: the job really exists even
            # though the client sees an exception.
            if self.db.committed:
                self.db.rows[self._row["id"]] = self._row
            raise RuntimeError(
                "RemoteProtocolError: server disconnected without sending a response"
            )
        matches = [
            {"id": row_id}
            for row_id, row in self.db.rows.items()
            if all(row.get(key) == value for key, value in self._filters)
        ]
        return SimpleNamespace(data=matches)


class _FakeSupabase:
    def __init__(self, *, committed: bool):
        self.committed = committed
        self.rows: dict[str, dict] = {}

    def table(self, _name: str):
        return _FakeTable(self)


@pytest.mark.asyncio
async def test_function_submit_survives_a_lost_insert_response(monkeypatch):
    db = _FakeSupabase(committed=True)
    monkeypatch.setattr(fn, "get_client", lambda: db)
    monkeypatch.setattr(fn.job_registry, "start", lambda *a, **k: "registered")

    response = await fn.predict_function_endpoint(
        request=None,
        body=fn.FunctionPredictRequest(pdb_id="1CRN"),
        user_id="user-1",
    )

    assert response.status == "queued"
    assert response.job_id in db.rows
    assert len(db.rows) == 1


@pytest.mark.asyncio
async def test_function_submit_still_fails_when_the_row_was_not_inserted(monkeypatch):
    db = _FakeSupabase(committed=False)
    monkeypatch.setattr(fn, "get_client", lambda: db)

    with pytest.raises(RuntimeError, match="RemoteProtocolError"):
        await fn.predict_function_endpoint(
            request=None,
            body=fn.FunctionPredictRequest(pdb_id="1CRN"),
            user_id="user-1",
        )


def test_stuck_cutoff_is_query_safe_and_still_a_timestamp():
    encoded = worker._stuck_cutoff(90)

    # A raw "+" in a query string is decoded as a space by PostgREST.
    assert "+" not in encoded
    parsed = datetime.fromisoformat(unquote(encoded))
    assert parsed.tzinfo is not None
    age = (datetime.now(timezone.utc) - parsed).total_seconds()
    assert age == pytest.approx(90 * 60, abs=10)


def test_stuck_sweep_requests_carry_no_raw_offset(monkeypatch):
    import httpx

    seen: list[str] = []

    def fake_get(url, *_args, **_kwargs):
        seen.append(url)
        return SimpleNamespace(status_code=200, json=list)

    monkeypatch.setattr(httpx, "get", fake_get)

    assert worker._sweep_stuck("docking_jobs") == 0
    assert seen, "sweep must issue its queries"
    for url in seen:
        assert "+" not in url.split("?", 1)[1]
        assert "lt." in url
