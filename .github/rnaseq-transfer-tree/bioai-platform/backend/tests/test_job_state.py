"""Durable mirror for in-process background jobs (app/services/job_state.py).

These tests pin the behaviour the feature exists for: a restart must not silently
erase a job, and a job interrupted by a restart must be reported as interrupted
rather than as either "still running" or "finished with no result".
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.services import job_state


class _FakeQuery:
    """Minimal stand-in for a PostgREST query builder.

    Records rows by job_id so tests can assert what a restart would read back,
    and lets a test simulate the table being missing or Supabase being down.
    """

    def __init__(self, table: str, store: dict, fail: bool = False):
        self.table_name = table
        self.store = store
        self.fail = fail
        self._filters: list[tuple[str, object]] = []
        self._order: tuple[str, bool] = ("created_at", True)
        self._limit = 100
        self._not_in: tuple[str, list] | None = None
        self._in: tuple[str, list] | None = None
        self._lt: tuple[str, object] | None = None
        self._payload: dict | None = None

    # builder methods
    def select(self, *a, **k):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def in_(self, key, values):
        self._in = (key, list(values))
        return self

    @property
    def not_(self):
        return _NotBuilder(self)

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def lt(self, key, value):
        self._lt = (key, value)
        return self

    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        return self

    def update(self, payload):
        self._payload = payload
        return self

    def delete(self):
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("supabase unavailable")
        if self._payload is not None:
            key = self._payload.get("job_id") or self._payload.get("id")
            self.store[key] = self._payload
            return type("R", (), {"data": [self._payload]})()
        if self.table_name == "transient_jobs":
            rows = [
                {
                    "job_id": k,
                    "kind": v.get("kind"),
                    "status": v.get("status"),
                    "state": v.get("state", {}),
                }
                for k, v in self.store.items()
            ]
            for key, value in self._filters:
                rows = [r for r in rows if r.get(key) == value]
            if self._in:
                key, values = self._in
                rows = [r for r in rows if r.get(key) in values]
            if self._not_in:
                key, values = self._not_in
                rows = [r for r in rows if r.get(key) not in values]
            key, desc = self._order
            rows.sort(key=lambda r: str(r.get(key)), reverse=desc)
            return type("R", (), {"data": rows[: self._limit]})()
        return type("R", (), {"data": []})()


class _NotBuilder:
    """PostgREST-py exposes ``.not_.in_(...)``; the negation applies to the query."""

    def __init__(self, query):
        self._query = query

    def in_(self, key, values):
        self._query._not_in = (key, list(values))
        return self._query


class _FakeClient:
    def __init__(self, store: dict, fail: bool = False):
        self.store = store
        self.fail = fail

    def table(self, name):
        return _FakeQuery(name, self.store, self.fail)


def _patch_client(monkeypatch, store, fail=False, configured=True):
    monkeypatch.setattr(job_state, "_client", lambda: _FakeClient(store, fail) if configured else None)
    monkeypatch.setattr(job_state, "_supabase_configured", lambda: configured)


# ── status derivation ────────────────────────────────────────────────────────


def test_derive_status_prefers_explicit_status():
    assert job_state._derive_status({"status": "complete", "phase": "error"}) == "complete"


def test_derive_status_maps_phylo_phase_convention():
    # phylo tracks its lifecycle in `phase` and has no `status` key at all.
    assert job_state._derive_status({"phase": "complete"}) == "complete"
    assert job_state._derive_status({"phase": "error"}) == "failed"
    assert job_state._derive_status({"phase": "tree_running"}) == "running"


# ── mirroring ────────────────────────────────────────────────────────────────


def test_save_mirrors_state(monkeypatch):
    store: dict = {}
    _patch_client(monkeypatch, store)
    job_state.save_job_state("j1", "phylo", {"status": "running", "phase": "msa_running"})
    assert store["j1"]["kind"] == "phylo"
    assert store["j1"]["status"] == "running"
    assert store["j1"]["phase"] == "msa_running"


def test_save_derives_terminal_status_from_phase(monkeypatch):
    store: dict = {}
    _patch_client(monkeypatch, store)
    job_state.save_job_state("j2", "phylo", {"phase": "complete", "newick": "(a,b);"})
    assert store["j2"]["status"] == "complete"


def test_save_never_raises_when_supabase_down(monkeypatch):
    store: dict = {}
    _patch_client(monkeypatch, store, fail=True)
    # Durability is a side effect: a database outage must not fail the job.
    job_state.save_job_state("j3", "phylo", {"status": "running"})


def test_save_no_op_when_not_configured(monkeypatch):
    store: dict = {}
    _patch_client(monkeypatch, store, configured=False)
    job_state.save_job_state("j4", "phylo", {"status": "running"})
    assert store == {}


def test_oversized_state_is_truncated(monkeypatch):
    store: dict = {}
    _patch_client(monkeypatch, store)
    big = {"status": "complete", "newick": "x" * (job_state.MAX_STATE_CHARS + 10)}
    job_state.save_job_state("j5", "phylo", big)
    assert store["j5"]["state"]["_truncated"] is True
    assert store["j5"]["status"] == "complete"  # status survives truncation


# ── restart reconciliation ───────────────────────────────────────────────────


def test_reconcile_restores_finished_and_fails_interrupted(monkeypatch):
    store = {
        "done": {"job_id": "done", "kind": "phylo", "status": "complete",
                 "state": {"status": "complete", "phase": "complete", "newick": "(a,b);"}},
        "gone": {"job_id": "gone", "kind": "phylo", "status": "running",
                 "state": {"status": "running", "phase": "tree_running"}},
    }
    _patch_client(monkeypatch, store)

    hydrated: dict = {}
    interrupted = job_state.reconcile_on_startup("phylo", lambda jid, st: hydrated.__setitem__(jid, st))

    assert interrupted == 1
    # A completed job is served again after the restart.
    assert hydrated["done"]["newick"] == "(a,b);"
    # An interrupted job is terminal and says why, instead of hanging on "running".
    assert hydrated["gone"]["status"] == "interrupted"
    assert "re-run" in hydrated["gone"]["error"].lower()
    assert store["gone"]["status"] == "interrupted"


def test_reconcile_skips_truncated_finished_state(monkeypatch):
    store = {
        "big": {"job_id": "big", "kind": "phylo", "status": "complete",
                "state": {"status": "complete", "_truncated": True}},
    }
    _patch_client(monkeypatch, store)

    hydrated: dict = {}
    job_state.reconcile_on_startup("phylo", lambda jid, st: hydrated.__setitem__(jid, st))
    # Serving a payload we know is incomplete would be worse than a 404.
    assert hydrated == {}


def test_reconcile_noop_without_supabase(monkeypatch):
    _patch_client(monkeypatch, {}, configured=False)
    assert job_state.reconcile_on_startup("phylo", lambda *a: None) == 0


def test_reconcile_survives_supabase_outage(monkeypatch):
    _patch_client(monkeypatch, {}, fail=True)
    assert job_state.reconcile_on_startup("phylo", lambda *a: None) == 0


# ── non-blocking mirror ──────────────────────────────────────────────────────


def test_mirror_does_not_block_and_preserves_last_state(monkeypatch):
    """``mirror`` must return immediately and still persist the final state.

    Callers are async request handlers that patch job state many times per run; a
    synchronous Supabase round-trip inline would block the event loop each time.
    """
    store: dict = {}
    _patch_client(monkeypatch, store)

    job_state.mirror("j6", "phylo", {"status": "running", "phase": "msa_running"})
    job_state.mirror("j6", "phylo", {"status": "running", "phase": "tree_running"})
    job_state.mirror("j6", "phylo", {"status": "complete", "phase": "complete"})

    # A single worker keeps writes ordered, so the last write wins.
    job_state._mirror_pool.shutdown(wait=True)
    job_state._mirror_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job-mirror")

    assert store["j6"]["status"] == "complete"
    assert store["j6"]["phase"] == "complete"


def test_mirror_survives_submit_failure(monkeypatch):
    """A dead pool must not turn a finishing job into an exception."""

    class _DeadPool:
        def submit(self, *a, **k):
            raise RuntimeError("interpreter shutdown")

    monkeypatch.setattr(job_state, "_mirror_pool", _DeadPool())
    store: dict = {}
    _patch_client(monkeypatch, store)
    job_state.mirror("j7", "phylo", {"status": "complete"})
    assert store["j7"]["status"] == "complete"
