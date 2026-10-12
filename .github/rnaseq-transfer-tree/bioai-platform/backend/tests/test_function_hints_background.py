"""The de novo GO-term prediction can also be an unfinished InterProScan job.

``function_hints`` runs inside the ``uniprot`` annotation bundle, so its
background poller has to merge the finished prediction into the bundle of
composition + GO terms instead of replacing the whole step payload the way the
domains poller does. These tests pin the merge, the hold-open contract, and the
upstream-failure verdict.
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


def _install_job(job_id: str, data: dict):
    pv._jobs[job_id] = {
        "status": "running",
        "steps": {"uniprot": {"status": "running", "progress": 50, "data": data}},
        "context": {},
    }


def _no_mirror(monkeypatch):
    monkeypatch.setattr(pv, "_mirror", lambda job_id: None)
    monkeypatch.setattr(pv, "_persist_v2_final", lambda *a, **k: None)

    async def _noop_finalize(job_id, context):
        pass

    monkeypatch.setattr(pv, "_finalize_context", _noop_finalize)


def _mark(job_id: str):
    return lambda step, status, **kw: pv._set_step_status(job_id, step, status, **kw)


def test_function_hints_poll_merges_into_annotation_bundle(monkeypatch):
    """The finished prediction lands next to composition, not in its place."""
    job_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _install_job(job_id, {"_de_novo": True, "composition": {"aa": 1}})
    _no_mirror(monkeypatch)

    prediction = {
        "status": "inferred",
        "go_terms": [{"go_id": "GO:0003674", "name": "molecular function", "namespace": "MF"}],
        "source": "interpro2go",
    }

    async def _ok(_job_id):
        return {"status": "complete", "source": "interproscan6", "domains": []}

    monkeypatch.setattr("app.services.de_novo.await_interpro_result", _ok)
    monkeypatch.setattr(
        "app.tools.function_predict.prediction_from_result",
        lambda result, seq, pdb_id="de_novo": prediction,
    )

    context: dict = {}

    async def drive():
        pv._schedule_function_hints_poll(
            "ipr_job_1", _mark(job_id), job_id, context, "ACDEFGHIKLM", None
        )
        assert pv._interpro_pending(job_id) == 1
        pv._complete_job(job_id, context, None)
        assert pv._get_job(job_id)["status"] == "running", (
            "parent must stay open while the GO prediction is finishing"
        )
        await asyncio.gather(*list(pv._INTERPRO_POLL_TASKS))

    asyncio.run(drive())

    bundle = pv._get_job(job_id)["steps"]["uniprot"]["data"]
    assert bundle["composition"] == {"aa": 1}, "composition must survive the merge"
    assert bundle["function_hints"] is prediction
    assert pv._get_job(job_id)["steps"]["uniprot"]["status"] == "complete"
    assert context["uniprot"]["function_hints"] is prediction
    assert pv._get_job(job_id)["status"] == "complete", "parent released after the last poll"
    assert job_id not in pv._INTERPRO_PENDING


def test_function_hints_upstream_failure_is_evidence_unavailable(monkeypatch):
    """A scan that fails upstream must read as unavailable, never 'no GO terms'."""
    job_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    _install_job(job_id, {"_de_novo": True, "composition": {"aa": 1}})
    _no_mirror(monkeypatch)

    async def _boom(_job_id):
        return {"status": "failed", "source": "interproscan6",
                "error": "InterProScan job failed upstream: ERROR"}

    monkeypatch.setattr("app.services.de_novo.await_interpro_result", _boom)
    monkeypatch.setattr(
        "app.tools.function_predict.prediction_from_result",
        lambda result, seq, pdb_id="de_novo": {
            "status": "evidence_unavailable",
            "go_terms": [],
            "source": "interpro2go",
            "retrieval_failures": [result["error"]],
        },
    )

    context: dict = {}

    async def drive():
        pv._schedule_function_hints_poll(
            "ipr_job_2", _mark(job_id), job_id, context, "ACDEFGHIKLM", None
        )
        pv._complete_job(job_id, context, None)
        await asyncio.gather(*list(pv._INTERPRO_POLL_TASKS))

    asyncio.run(drive())

    fh = pv._get_job(job_id)["steps"]["uniprot"]["data"]["function_hints"]
    assert fh["status"] == "evidence_unavailable"
    assert "failed upstream" in fh["retrieval_failures"][0]
    assert pv._get_job(job_id)["steps"]["uniprot"]["status"] == "complete", (
        "an upstream failure is a verdict, not a step crash: the bundle is done"
    )
    assert pv._get_job(job_id)["status"] == "complete"
