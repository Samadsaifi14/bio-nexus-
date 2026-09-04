"""Scientific-integrity tests for the research-grade function module."""

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
