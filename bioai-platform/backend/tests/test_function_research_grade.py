"""Scientific-integrity tests for the research-grade function module."""

import asyncio

import pytest

from app.tools import function_predict as fp


def test_interpro_go_terms_do_not_report_uncalibrated_probability(monkeypatch):
    hits = [
        {"accession": "IPR000001", "name": "A", "database": "InterPro", "start": 1, "end": 20},
        {"accession": "IPR000002", "name": "B", "database": "InterPro", "start": 30, "end": 50},
    ]

    mapping = {
        "IPR000001": [{"id": "GO:0000001", "name": "example", "category": "BP"}],
        "IPR000002": [{"id": "GO:0000001", "name": "example", "category": "BP"}],
    }
    monkeypatch.setattr(fp, "_fetch_interpro_go_terms", lambda accession: mapping[accession])

    terms = fp._interpro_to_go(hits)
    assert len(terms) == 1
    assert terms[0]["support_count"] == 2
    assert terms[0]["supporting_interpro_entries"] == ["IPR000001", "IPR000002"]
    assert terms[0]["confidence"] is None
    assert "No calibrated probability" in terms[0]["confidence_note"]
    assert terms[0]["evidence_type"] == "interpro2go_mapping"


def test_no_interpro_evidence_does_not_fabricate_go_terms(monkeypatch):
    monkeypatch.setattr(fp, "_fetch_pdb_sequence", lambda _pdb: "ACDEFGHIKLMNPQRSTVWY")
    monkeypatch.setattr(fp, "_run_interproscan", lambda _sequence: [])

    result = fp.predict_function("1abc")

    assert result["status"] == "insufficient_evidence"
    assert result["go_terms"] == []
    assert result["ec_numbers"] == []
    assert result["saliency"] == []
    assert len(result["residue_chemistry_scores"]) == result["sequence_length"]
    assert "not model saliency" in result["residue_chemistry_note"].lower()
    assert "does not substitute" in result["note"]


def test_interpro_mapping_is_reported_as_inference_not_experimental_annotation(monkeypatch):
    monkeypatch.setattr(fp, "_fetch_pdb_sequence", lambda _pdb: "ACDEFGHIKLMNPQRSTVWY")
    monkeypatch.setattr(
        fp,
        "_run_interproscan",
        lambda _sequence: [
            {"accession": "IPR000001", "name": "Example", "database": "InterPro", "start": 1, "end": 20, "score": None}
        ],
    )
    monkeypatch.setattr(
        fp,
        "_fetch_interpro_go_terms",
        lambda _accession: [{"id": "GO:0003674", "name": "molecular function", "category": "MF"}],
    )

    result = fp.predict_function("1abc")

    assert result["status"] == "inferred"
    assert result["method"] == "interpro2go"
    assert result["go_terms"][0]["confidence"] is None
    assert result["provenance"]["go_mapping_source"] == "InterPro2GO via InterPro API"
    assert "not direct experimental annotations" in result["note"]


def test_ec_scope_is_explicit(monkeypatch):
    monkeypatch.setattr(fp, "_fetch_pdb_sequence", lambda _pdb: "ACDEFGHIK")
    monkeypatch.setattr(fp, "_run_interproscan", lambda _sequence: [])

    result = fp.predict_function("1abc")

    assert result["ec_numbers"] == []
    assert "not implemented" in result["ec_scope_note"]


def test_retrieval_failure_is_reported_as_failure_not_as_absent_evidence(monkeypatch):
    """A failed lookup must not masquerade as a protein with no InterPro2GO mapping."""
    monkeypatch.setattr(fp, "_fetch_pdb_sequence", lambda _pdb: "ACDEFGHIKLMNPQRSTVWY")

    def _outage(*_args, **_kwargs):
        raise OSError("simulated network outage")

    monkeypatch.setattr(fp.urllib.request, "urlopen", _outage)

    result = fp.predict_function("1abc")

    assert result["status"] == "evidence_unavailable"
    assert result["method"] == "interpro2go_retrieval_failed"
    # The core research-grade guarantee is unchanged: no GO term is invented.
    assert result["go_terms"] == []
    assert result["ec_numbers"] == []
    # Provenance must not claim a live retrieval that never happened.
    assert result["provenance"]["retrieval_is_live"] is False
    assert result["provenance"]["retrieval_failures"]
    assert "retrieval failure" in result["note"].lower()
    assert "does not substitute" in result["note"]


def test_successful_lookup_with_no_mapping_stays_insufficient_evidence(monkeypatch):
    """A completed scan that simply matched nothing is genuine insufficient evidence."""
    monkeypatch.setattr(fp, "_fetch_pdb_sequence", lambda _pdb: "ACDEFGHIKLMNPQRSTVWY")
    monkeypatch.setattr(fp, "_run_interproscan", lambda _sequence: [])

    result = fp.predict_function("1abc")

    assert result["status"] == "insufficient_evidence"
    assert result["method"] == "interpro2go_no_evidence"
    assert result["provenance"]["retrieval_is_live"] is True
    assert result["provenance"]["retrieval_failures"] == []


# ── Async de novo sequence path (the pipeline's function_hints) ─────────────


@pytest.mark.asyncio
async def test_predict_from_sequence_returns_running_marker(monkeypatch):
    async def fake_search(sequence, email=""):
        return {"status": "running", "domains": [], "interpro_job_id": "iprscan-abc"}

    monkeypatch.setattr("app.services.de_novo.interpro_sequence_search", fake_search)

    result = await fp._predict_from_sequence("ACDEFGHIKLMNPQRSTVWY", pdb_id="de_novo")

    assert result["status"] == "running"
    assert result["interpro_job_id"] == "iprscan-abc"
    assert result["go_terms"] == []
    assert result["sequence_length"] == 20
    assert "still running" in result["note"]


@pytest.mark.asyncio
async def test_predict_from_sequence_complete_maps_go(monkeypatch):
    async def fake_search(sequence, email=""):
        return {
            "status": "complete",
            "domains": [
                {"accession": "IPR000001", "name": "A", "source_db": "PFAM", "start": 1, "end": 20}
            ],
        }

    monkeypatch.setattr("app.services.de_novo.interpro_sequence_search", fake_search)
    monkeypatch.setattr(
        fp,
        "_fetch_interpro_go_terms",
        lambda accession: [{"id": "GO:0000001", "name": "example", "category": "BP"}],
    )

    result = await fp._predict_from_sequence("ACDEFGHIKLMNPQRSTVWY", pdb_id="de_novo")

    assert result["status"] == "inferred"
    assert result["method"] == "interpro2go"
    assert result["go_terms"][0]["go_id"] == "GO:0000001"
    assert result["domain_hits"][0]["database"] == "PFAM"
    assert result["provenance"]["sequence_source"] == "user-submitted sequence"


@pytest.mark.asyncio
async def test_predict_from_sequence_submission_failure_is_evidence_unavailable(monkeypatch):
    async def fake_search(sequence, email=""):
        raise OSError("EBI unreachable")

    monkeypatch.setattr("app.services.de_novo.interpro_sequence_search", fake_search)

    result = await fp._predict_from_sequence("ACDEFGHIKLMNPQRSTVWY", pdb_id="de_novo")

    assert result["status"] == "evidence_unavailable"
    assert result["method"] == "interpro2go_retrieval_failed"
    assert result["go_terms"] == []
    assert result["provenance"]["retrieval_is_live"] is False


def test_prediction_from_result_reports_evidence_unavailable(monkeypatch):
    result = fp.prediction_from_result(
        {"status": "failed", "error": "InterProScan job failed upstream: ERROR"},
        "ACDEFGHIKLMNPQRSTVWY",
        pdb_id="de_novo",
    )

    assert result["status"] == "evidence_unavailable"
    assert result["method"] == "interpro2go_retrieval_failed"
    assert result["go_terms"] == []
    assert "failed upstream" in result["note"]


def test_prediction_from_result_empty_scan_is_insufficient(monkeypatch):
    result = fp.prediction_from_result(
        {"status": "complete", "domains": []}, "ACDEFGHIKLMNPQRSTVWY", pdb_id="de_novo"
    )

    assert result["status"] == "insufficient_evidence"
    assert result["method"] == "interpro2go_no_evidence"
    assert result["provenance"]["retrieval_failures"] == []
