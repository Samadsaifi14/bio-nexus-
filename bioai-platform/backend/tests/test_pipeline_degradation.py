"""Degraded-but-complete pipeline runs.

Live evidence (job 50ee96cf-...): the wizard failed with

    Pipeline failed at uniprot: UniProt returned 500 for P61260

A single transient provider error for one BLAST hit discarded an otherwise valid
search. UniProt annotation is degradable — domains, structure and interpretation
all have sequence-only fallbacks — so the run must complete and report the
degraded step instead of failing outright.
"""

from __future__ import annotations

import pytest

from app.routers import pipeline_v2 as pv


@pytest.mark.asyncio
async def test_uniprot_provider_error_degrades_instead_of_failing_run(monkeypatch):
    job_id = "uniprot-degraded-1"

    async def fake_blast(*_a, **_k):
        hit = {"accession": "P61260", "description": "hypothetical protein"}
        return {"count": 1, "hits": [hit], "top_hit": hit}

    async def fake_uniprot(_candidate, query_sequence=None, try_sequence=True):
        return {"error": "UniProt returned 500 for P61260"}

    domain_calls: dict = {}

    async def fake_domains(sequence, accession, resolved):
        domain_calls["accession"] = accession
        domain_calls["resolved"] = resolved
        return {
            "uniprot_accession": None,
            "sequence_length": len(sequence),
            "domains": [],
            "source": "interproscan6",
            "status": "complete",
        }

    async def fake_alphafold(_context, _sequence, _accession, _resolved):
        return {"structure_available": True, "source": "esmfold"}

    async def fake_msa(*_a, **_k):
        return {"error": "skip", "aln_fasta": None, "phylotree": None}

    async def fake_pathway(_context):
        return {"pathways": []}

    async def fake_interpret(_context):
        return {"interpretation": "degraded but usable"}

    async def fake_finalize(*_a, **_k):
        return None

    persisted: dict = {}

    def fake_persist(_job_id, status, _context, error=None):
        persisted.update(status=status, error=error)

    monkeypatch.setattr(pv, "_run_blast", fake_blast)
    monkeypatch.setattr(pv, "_run_uniprot", fake_uniprot)
    monkeypatch.setattr(pv, "_run_domains_or_denovo", fake_domains)
    monkeypatch.setattr(pv, "_run_alphafold_or_esmfold", fake_alphafold)
    monkeypatch.setattr(pv, "_run_msa", fake_msa)
    monkeypatch.setattr(pv, "_run_pathway_enrichment", fake_pathway)
    monkeypatch.setattr(pv, "_run_interpret", fake_interpret)
    monkeypatch.setattr(pv, "_persist_blast_preview", lambda *_a, **_k: None)
    monkeypatch.setattr(pv, "_finalize_context", fake_finalize)
    monkeypatch.setattr(pv, "_persist_v2_final", fake_persist)

    pv._jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "steps": {
            step: {"status": "pending", "progress": 0, "data": None, "error": None}
            for step in pv.STEP_ORDER
        },
    }

    try:
        await pv._execute(
            job_id, "MEEPQSDPSVEPPLSQETFSDLWKLLPENNV", list(pv.STEP_ORDER)
        )
        job = pv._jobs[job_id]
    finally:
        pv._jobs.pop(job_id, None)

    assert job["status"] == "complete", job.get("error")
    assert persisted["status"] == "complete"
    assert persisted["error"] is None

    # The failed provider call is visible, but it is not fatal.
    assert job["steps"]["uniprot"]["status"] == "failed"
    assert "500" in job["steps"]["uniprot"]["error"]
    assert job["context"]["uniprot"]["resolved_uniprot"] is False
    assert job["context"]["degraded_steps"] == [
        {"step": "uniprot", "reason": "UniProt returned 500 for P61260"}
    ]

    # Downstream steps fell back to sequence-only inputs. The original BLAST
    # accession is retained for provenance, but it is explicitly not treated as
    # a resolved UniProt entry.
    assert domain_calls == {"accession": "P61260", "resolved": False}
    assert job["context"]["interpret"]["interpretation"] == "degraded but usable"


@pytest.mark.asyncio
async def test_blast_failure_is_still_fatal(monkeypatch):
    """Only BLAST is non-degradable: without hits there is nothing to analyse."""
    job_id = "blast-fatal-1"

    async def fake_blast(*_a, **_k):
        return {"error": "BLAST provider unavailable", "search_complete": False, "hits": []}

    persisted: dict = {}

    def fake_persist(_job_id, status, _context, error=None):
        persisted.update(status=status, error=error)

    monkeypatch.setattr(pv, "_run_blast", fake_blast)
    monkeypatch.setattr(pv, "_persist_v2_final", fake_persist)
    monkeypatch.setattr(pv, "_finalize_context", lambda *_a, **_k: None)

    pv._jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "steps": {
            step: {"status": "pending", "progress": 0, "data": None, "error": None}
            for step in pv.STEP_ORDER
        },
    }

    try:
        await pv._execute(job_id, "MEEPQSDPSVEPPLSQETFSDLWKLLPENNV", list(pv.STEP_ORDER))
        job = pv._jobs[job_id]
    finally:
        pv._jobs.pop(job_id, None)

    assert job["status"] == "failed"
    assert persisted["status"] == "failed"
    assert "BLAST provider unavailable" in persisted["error"]
