"""A de novo InterProScan6 job finishes long after the pipeline's other steps.

The parent job therefore cannot be reported terminal while the domains step is
still running upstream: PipelineResults.tsx stops polling and navigates to the
report the instant it sees `complete`, so a parent closed here would hide the
background result permanently. These tests pin that contract, plus the durable
context update the finished result has to make.
"""

import asyncio

import pytest

from app.routers import pipeline_v2 as pv


@pytest.fixture(autouse=True)
def _clean_registry():
    pv._INTERPRO_PENDING.clear()
    pv._INTERPRO_DEFERRED.clear()
    pv._INTERPRO_POLL_TASKS.clear()
    yield
    pv._INTERPRO_PENDING.clear()
    pv._INTERPRO_DEFERRED.clear()
    pv._INTERPRO_POLL_TASKS.clear()


def _install_job(job_id: str, status: str = "running", steps: dict | None = None):
    pv._jobs[job_id] = {
        "status": status,
        "steps": steps if steps is not None else {},
        "context": {},
    }


def _no_mirror(monkeypatch):
    monkeypatch.setattr(pv, "_mirror", lambda job_id: None)
    monkeypatch.setattr(pv, "_persist_v2_final", lambda *a, **k: None)


def test_parent_stays_running_while_interpro_outstanding(monkeypatch):
    job_id = "11111111-1111-1111-1111-111111111111"
    _install_job(job_id, steps={"blast": {"status": "complete", "progress": 100}})
    _no_mirror(monkeypatch)

    finalized = []
    with pv._jobs_lock:
        pv._INTERPRO_PENDING[job_id] = 1

    pv._complete_job(job_id, {"blast": {}}, lambda: finalized.append("done"))

    assert pv._get_job(job_id)["status"] == "running", (
        "parent went terminal while a background InterPro poll was outstanding"
    )
    assert job_id in pv._INTERPRO_DEFERRED
    assert finalized == [], "provenance/experiment finalize must wait for the domains"


def test_last_poll_settling_completes_the_parent(monkeypatch):
    job_id = "22222222-2222-2222-2222-222222222222"
    _install_job(job_id, steps={"domains": {"status": "running", "progress": 50}})
    _no_mirror(monkeypatch)

    finalized = []
    with pv._jobs_lock:
        pv._INTERPRO_PENDING[job_id] = 1
        pv._INTERPRO_DEFERRED.add(job_id)

    context = {"domains": {"status": "running", "interpro_job_id": "x"}}
    _interpro_settle_result = {
        "status": "complete",
        "source": "interproscan6",
        "domains": [{"entry": "IPR000719", "name": "Protein kinase, catalytic"}],
    }
    with pv._jobs_lock:
        context["domains"] = _interpro_settle_result

    pv._interpro_settle(job_id, context, lambda: finalized.append("done"))

    assert pv._get_job(job_id)["status"] == "complete"
    assert job_id not in pv._INTERPRO_DEFERRED
    assert job_id not in pv._INTERPRO_PENDING
    assert finalized == ["done"]


def test_settle_without_an_outstanding_poll_is_a_noop(monkeypatch):
    """InterPro finished before the pipeline did: the normal path closes the job."""
    job_id = "33333333-3333-3333-3333-333333333333"
    _install_job(job_id)
    _no_mirror(monkeypatch)

    finalized = []
    pv._interpro_settle(job_id, {}, lambda: finalized.append("done"))

    assert pv._get_job(job_id)["status"] == "running", "must not close a job it never held"
    assert finalized == []


def test_settle_does_not_override_a_failed_pipeline(monkeypatch):
    job_id = "44444444-4444-4444-4444-444444444444"
    _install_job(job_id, status="failed")
    _no_mirror(monkeypatch)

    with pv._jobs_lock:
        pv._INTERPRO_PENDING[job_id] = 1
        pv._INTERPRO_DEFERRED.add(job_id)

    pv._interpro_settle(job_id, {}, lambda: None)

    assert pv._get_job(job_id)["status"] == "failed", (
        "a late InterPro result must not paper over a pipeline failure"
    )


def test_complete_job_completes_immediately_when_nothing_is_pending(monkeypatch):
    job_id = "55555555-5555-5555-5555-555555555555"
    _install_job(job_id)
    _no_mirror(monkeypatch)

    finalized = []
    pv._complete_job(job_id, {"blast": {"status": "complete"}}, lambda: finalized.append("done"))

    assert pv._get_job(job_id)["status"] == "complete"
    assert finalized == ["done"]


def test_poll_failure_still_releases_the_parent(monkeypatch):
    """A failed InterPro poll must not strand the job in `running` forever."""
    job_id = "66666666-6666-6666-6666-666666666666"
    _install_job(job_id, steps={"domains": {"status": "running", "progress": 50}})
    _no_mirror(monkeypatch)

    marks = []

    async def _boom(job_id_arg):
        raise RuntimeError("EBI unreachable")

    monkeypatch.setattr("app.services.de_novo.await_interpro_result", _boom)

    async def drive():
        # The real order: the poll is scheduled during the step, and only then does
        # the pipeline reach its end and discover a poll is outstanding.
        pv._schedule_interpro_poll(
            "ipr_job_1",
            lambda step, status, **kw: marks.append((step, status)),
            "domains",
            job_id,
            {},
        )
        assert pv._interpro_pending(job_id) == 1
        pv._complete_job(job_id, {}, None)
        assert pv._get_job(job_id)["status"] == "running"

        tasks = list(pv._INTERPRO_POLL_TASKS)
        assert tasks, "poll task was not scheduled"
        await asyncio.gather(*tasks)

    asyncio.run(drive())

    assert ("domains", "failed") in marks
    assert pv._get_job(job_id)["status"] == "complete", (
        "the parent must be released once the last poll fails"
    )
    assert job_id not in pv._INTERPRO_PENDING


def test_successful_poll_rebuilds_the_report(monkeypatch):
    """final_report and the InterPro source capture are both built from the domains.

    They are produced while the result is still pending, so the last poll has to
    rebuild them; otherwise the report permanently carries the placeholder.
    """
    job_id = "88888888-8888-8888-8888-888888888888"
    _install_job(job_id, steps={"domains": {"status": "running", "progress": 50}})
    _no_mirror(monkeypatch)

    domains = [{"accession": "IPR000719", "name": "Protein kinase, catalytic"}]
    rebuilt = []

    async def _ok(job_id_arg):
        return {"status": "complete", "source": "interproscan6", "domains": domains}

    monkeypatch.setattr("app.services.de_novo.await_interpro_result", _ok)

    async def _fake_finalize(jid, ctx):
        rebuilt.append((jid, ctx["domains"].get("domains")))

    monkeypatch.setattr(pv, "_finalize_context", _fake_finalize)

    context: dict = {}

    async def drive():
        pv._schedule_interpro_poll(
            "ipr_job_1", lambda step, status, **kw: None, "domains", job_id, context
        )
        pv._complete_job(job_id, context, None)
        await asyncio.gather(*list(pv._INTERPRO_POLL_TASKS))

    asyncio.run(drive())

    assert rebuilt == [(job_id, domains)], (
        "the report must be rebuilt from the real domains once they arrive"
    )


def test_successful_poll_fills_the_durable_context(monkeypatch):
    """The finished domains must land in the report context, not only on the step."""
    job_id = "77777777-7777-7777-7777-777777777777"
    _install_job(job_id, steps={"domains": {"status": "running", "progress": 50}})
    _no_mirror(monkeypatch)

    persisted = []
    monkeypatch.setattr(pv, "_persist_v2_final",
                        lambda jid, status, ctx, **k: persisted.append((jid, status, ctx)))

    domains = [{"entry": "IPR000719", "name": "Protein kinase, catalytic"}]

    async def _ok(job_id_arg):
        return {"status": "complete", "source": "interproscan6", "domains": domains}

    monkeypatch.setattr("app.services.de_novo.await_interpro_result", _ok)

    context: dict = {}

    async def drive():
        pv._schedule_interpro_poll(
            "ipr_job_1", lambda step, status, **kw: None, "domains", job_id, context
        )
        pv._complete_job(job_id, context, None)
        await asyncio.gather(*list(pv._INTERPRO_POLL_TASKS))

    asyncio.run(drive())

    assert context["domains"]["domains"] == domains
    assert pv._get_job(job_id)["steps"]["domains"]["status"] == "running"  # untouched by lambda mark
    assert persisted and persisted[0][1] == "complete"
    assert persisted[0][2]["domains"]["domains"] == domains, (
        "the persisted report must contain the domains, not the pending placeholder"
    )
