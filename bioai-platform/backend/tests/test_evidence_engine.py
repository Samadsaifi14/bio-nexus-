"""AI Evidence Engine (Component 9) unit tests — no DB, no binary deps."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.evidence_engine import evidence_engine
from app.services.evidence_graph import assemble_evidence, keyword_vocab, sentence_split

CONTEXT = {
    "blast": {
        "version": "2.14-test-fixture",
        "count": 12,
        "top_hit": {"accession": "P04637", "description": "Cellular tumor antigen p53", "identity_pct": 100.0},
        "hits": [{"accession": "P04637", "description": "p53", "identity_pct": 100.0}],
    },
    "uniprot": {"version": "test-pinned-release", "accession": "P04637", "full_name": "Cellular tumor antigen p53", "gene_names": ["TP53"], "organism": "Homo sapiens"},
    "domains": {"version": "test-pinned-release", "sequence_length": 393, "domains": [{"name": "p53", "accession": "IPR012345", "start": 92, "end": 292}]},
    "interpret": {
        "interpretation": "The query is tumour suppressor p53 (TP53, Homo sapiens). It contains a DNA-binding domain detected by InterPro. This result is consistent with prior literature hypotheses, though the exact binding cavity is not fully resolved by this run."
    },
}


def test_sentence_split_splits_on_period():
    parts = sentence_split("First sentence. Second one. Third!")
    assert parts[0].startswith("First")
    assert "Second one" in parts[1]


def test_sentence_split_empty():
    assert sentence_split("") == []


def test_keyword_vocab_has_sections():
    vocab = keyword_vocab(CONTEXT)
    assert "P04637" in vocab["blast"]
    assert "TP53" in vocab["uniprot"]
    assert "interpro" in vocab["domains"] or "Interpro" in vocab["domains"]


def test_assemble_evidence_sources_and_claims():
    graph = assemble_evidence(CONTEXT)
    source_ids = {s["id"] for s in graph["sources"]}
    assert "blast" in source_ids and "uniprot" in source_ids and "domains" in source_ids
    assert graph["claims"]
    assert all(c["id"].startswith("claim-") for c in graph["claims"])
    for edge in graph["edges"]:
        assert edge["from"] in source_ids


def test_evidence_validation_passes_on_supported_claims():
    result = evidence_engine.parse(assemble_evidence(CONTEXT))
    report = evidence_engine.validate(result)
    assert report.valid, [c for c in report.checks if not c["passed"]]
    stats = result.statistics
    assert stats["claims"] >= 2
    assert stats["supported"] >= 1


def test_evidence_validation_rejects_unsupported_claims():
    unsupported = {
        "sources": [{"id": "blast", "tool": "BLAST", "database": "nr", "version": "2.14"}],
        "claims": [
            {"id": "claim-1", "text": "Consensus: the protein binds calmodulin in vivo at 37C.", "evidence": [], "rejected": False},
        ],
        "edges": [],
    }
    report = evidence_engine.validate(evidence_engine.parse(unsupported))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "honest_claims" in names


def test_evidence_validation_bad_reference():
    bad = {
        "sources": [{"id": "blast", "tool": "BLAST", "database": "nr", "version": "2.14"}],
        "claims": [{"id": "c1", "text": "x" * 40, "confidence": "high", "evidence": ["ghost"], "rejected": False}],
        "edges": [],
    }
    report = evidence_engine.validate(evidence_engine.parse(bad))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "graph_reference" in names


def test_evidence_engine_describe():
    desc = evidence_engine.describe()
    assert desc["name"] == "evidence"
    assert desc["version"] == "1.0.0"
    assert "honesty" in desc["parameters"]


def test_evidence_export_csv():
    result = evidence_engine.parse(assemble_evidence(CONTEXT))
    csv = evidence_engine.export(result, "csv")
    assert csv.startswith("claim_id,claim,confidence,evidence,rejected")
    assert "claim-1" in csv


def test_evidence_figure_svg():
    result = evidence_engine.parse(assemble_evidence(CONTEXT))
    svg = evidence_engine.figure(result)
    assert svg.startswith("<svg")
    assert svg.count("<svg") == svg.count("</svg>")
    assert "AI evidence graph" in svg


def test_evidence_engine_smoke_parse_non_dict():
    report = evidence_engine.validate(evidence_engine.parse(None))
    stats = evidence_engine.parse(None).statistics
    assert stats["claims"] == 0
    assert not report.valid
