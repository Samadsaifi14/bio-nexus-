from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{label}: expected source block not found in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "bioai-platform/backend/app/routers/pipeline_v2.py",
    '''        zero_hits = result.get("count", 0) == 0
        if zero_hits and (detect_sequence_type(sequence) or "protein") == "protein":
            # Tier 6: no database match at all — characterize from sequence
            # alone instead of failing the run (techspec.md §1).
            denovo_mode = True
            result["_note"] = "No BLAST hits found — switching to de novo characterization"
            _mark("blast", "complete", progress=100, data=result)
        else:
            _mark("blast", "failed" if zero_hits else "complete", progress=100, data=result)
            if zero_hits:
                _failed_step = "blast"
                _failed_error = result.get("error", "No BLAST hits found")
        context["blast"] = result
''',
    '''        provider_failed = bool(result.get("error")) or result.get("search_complete") is False
        zero_hits = result.get("count", 0) == 0
        confirmed_zero_hits = zero_hits and not provider_failed

        if confirmed_zero_hits and (detect_sequence_type(sequence) or "protein") == "protein":
            # Enter de novo mode only after a provider completed normally and
            # explicitly returned zero hits. Network/provider failures are not
            # biological evidence of novelty.
            denovo_mode = True
            result["_note"] = "Completed BLAST search returned no hits — switching to de novo characterization"
            _mark("blast", "complete", progress=100, data=result)
        else:
            blast_failed = provider_failed or zero_hits
            _mark("blast", "failed" if blast_failed else "complete", progress=100, data=result)
            if blast_failed:
                _failed_step = "blast"
                _failed_error = result.get("error", "BLAST completed without usable hits")
        context["blast"] = result
''',
    "pipeline zero-hit integrity guard",
)

replace_once(
    "bioai-platform/backend/app/routers/pipeline_v2.py",
    '''    return {
        "count": len(hits),
        "source": source,
''',
    '''    return {
        "count": len(hits),
        "search_complete": True,
        "source": source,
''',
    "canonical BLAST completion marker",
)

replace_once(
    "bioai-platform/backend/app/routers/pipeline_v2.py",
    '''        return {"error": str(e), "count": 0, "hits": []}
''',
    '''        return {"error": str(e), "count": 0, "hits": [], "search_complete": False}
''',
    "BLAST parameter error marker",
)

replace_once(
    "bioai-platform/backend/app/routers/pipeline_v2.py",
    '''    logger.warning("EBI BLAST unavailable and NCBI failed (%s)", ncbi_error)
    return {"error": ncbi_error or "BLAST failed via EBI and NCBI", "count": 0, "hits": []}
''',
    '''    logger.warning("EBI BLAST unavailable and NCBI failed (%s)", ncbi_error)
    return {
        "error": ncbi_error or "BLAST failed via EBI and NCBI",
        "count": 0,
        "hits": [],
        "search_complete": False,
    }
''',
    "BLAST provider failure marker",
)

replace_once(
    "bioai-platform/backend/app/services/final_synthesis.py",
    '''    elif blast.get("count", 0) == 0:
        findings.append({
            "claim": "No significant similarity to any database sequence.",
''',
    '''    elif blast.get("search_complete") is True and blast.get("count", 0) == 0:
        findings.append({
            "claim": "No significant similarity was found in the completed BLAST search.",
''',
    "final-report zero-hit evidence guard",
)

replace_once(
    "bioai-platform/backend/app/tools/blast.py",
    '''        if last_error:
            logger.warning("EBI BLAST JSON retrieval failed for %s: %s", job_id, last_error)
        return []
''',
    '''        if last_error:
            logger.warning("EBI BLAST JSON retrieval failed for %s: %s", job_id, last_error)
            raise RuntimeError(f"EBI BLAST JSON retrieval failed: {last_error}") from last_error
        return []
''',
    "EBI JSON retrieval failure propagation",
)

replace_once(
    "bioai-platform/backend/app/tools/blast.py",
    '''        except Exception as exc:
            logger.warning("EBI BLAST XML fallback failed for %s: %s", job_id, exc)
            return []
''',
    '''        except Exception as exc:
            logger.warning("EBI BLAST XML fallback failed for %s: %s", job_id, exc)
            raise RuntimeError(f"EBI BLAST XML retrieval failed: {exc}") from exc
''',
    "EBI XML retrieval failure propagation",
)

Path("bioai-platform/backend/tests/test_blast_false_denovo_guard.py").write_text(
    '''import asyncio


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
''',
    encoding="utf-8",
)

print("BLAST integrity hotfix applied")
