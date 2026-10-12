import asyncio


def test_provider_error_is_not_treated_as_denovo(monkeypatch):
    from app.routers import pipeline_v2 as pv

    job_id = "guard-test"
    seq = "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEA"
    pv._jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "steps": {
            s: {"status": "pending", "progress": 0, "data": None, "error": None}
            for s in pv.STEP_ORDER
        },
        "requested_steps": ["blast"],
        "sequence": seq,
        "error": None,
    }

    async def fake_blast(*args, **kwargs):
        return {
            "error": "provider timeout",
            "count": 0,
            "hits": [],
            "search_complete": False,
        }

    async def forbidden_denovo(*args, **kwargs):
        raise AssertionError("de novo branch must not run on provider failure")

    monkeypatch.setattr(pv, "_run_blast", fake_blast)
    monkeypatch.setattr(pv, "_run_denovo_steps", forbidden_denovo)
    monkeypatch.setattr(pv, "_persist_v2_final", lambda *a, **k: None)
    monkeypatch.setattr(pv, "_capture_run_sources", lambda *a, **k: None)

    asyncio.run(pv._execute(job_id, seq, ["blast"]))
    job = pv._jobs[job_id]
    assert job["status"] == "failed"
    assert "provider timeout" in job["error"]
    assert job["steps"]["blast"]["status"] == "failed"
    pv._jobs.pop(job_id, None)
