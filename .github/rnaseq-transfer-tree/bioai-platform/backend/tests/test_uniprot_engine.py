"""Unit tests for the UniProt engine — scientific object contract.

No network, no DB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, get_engine
from app.services.benchmarks import _metric_value


CANONICAL = {
    "accession": "P01308",
    "full_name": "Insulin",
    "organism": "Homo sapiens",
    "gene_names": ["INS"],
    "functions": ["Hormone activity"],
    "keywords": ["Secreted", "Signal"],
    "subcellular_locations": ["Secreted"],
    "pdb_ids": ["1A7F"],
    "go_terms": ["C:extracellular region", "F:hormone activity", "P:peptide hormone processing"],
    "sequence": "MALWMRLLPLLALLALWGPD",
    "sequence_length": 20,
    "features": [{"type": "SIGNAL", "description": "Signal peptide"}],
    "resolution": {"uniprot_accession": "P01308", "method": "direct", "original_accession": "P01308"},
    "resolved_uniprot": True,
    "confidence": "identified",
}


def test_uniprot_engine_registered():
    assert "uniprot" in ENGINES
    assert get_engine("uniprot") is ENGINES["uniprot"]


def test_parse_maps_canonical_result():
    eng = get_engine("uniprot")
    res = eng.parse(CANONICAL)
    assert res.engine == "uniprot"
    assert res.tool == "UniProt"
    assert res.evidence["accession"] == "P01308"
    assert res.statistics["go_count"] == 3
    assert res.statistics["sequence_length"] == 20
    assert res.evidence["gene_names"] == ["INS"]


def test_parse_rejects_non_canonical():
    eng = get_engine("uniprot")
    try:
        eng.parse({"nonsense": True})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_validate_accepts_good_result():
    eng = get_engine("uniprot")
    assert eng.validate(eng.parse(CANONICAL)).valid


def test_validate_flags_missing_accession_and_bad_go():
    eng = get_engine("uniprot")
    bad = dict(CANONICAL, accession="")
    assert not eng.validate(eng.parse(bad)).valid

    bad_go = dict(CANONICAL, go_terms=["not-a-go-term"])
    report = eng.validate(eng.parse(bad_go))
    assert not report.valid
    assert any(c["name"] == "go_term_malformed" for c in report.checks)


def test_export_csv_go_rows():
    eng = get_engine("uniprot")
    out = eng.export(eng.parse(CANONICAL), "csv")
    lines = out.strip().splitlines()
    assert lines[0].startswith("accession,full_name")
    assert "F,hormone activity" in out
    assert len(lines) == 4  # header + 3 GO terms


def test_figure_svg():
    eng = get_engine("uniprot")
    svg = eng.figure(eng.parse(CANONICAL))
    assert svg.startswith("<?xml")
    assert "Molecular function" in svg
    assert "P01308" in svg


def test_benchmark_gene_name_metric_maps():
    context = {"uniprot": {"gene_names": ["TP53"], "accession": "P04637"}}
    assert _metric_value(context, "uniprot", "gene_name") == "TP53"
    empty = {"uniprot": {}}
    assert _metric_value(empty, "uniprot", "gene_name") is None


def test_describe_has_scientific_contract():
    eng = get_engine("uniprot")
    d = eng.describe()
    assert "UniProt Consortium" in d["citations"][0]
    assert "UNIPROT_P53_MUST_BE_TP53_GENE" in d["benchmarks"]
    assert "csv" in d["export_formats"]