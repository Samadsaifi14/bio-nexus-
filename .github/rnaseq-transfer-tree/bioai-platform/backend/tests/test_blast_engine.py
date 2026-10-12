"""Unit tests for the BLAST engine — scientific object contract.

No network, no DB: parse/validate/export/figure/citation are all pure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.base import EngineResult, ValidationReport
from app.engines import ENGINES, get_engine


CANONICAL = {
    "count": 2,
    "source": "ebi",
    "database": "swissprot",
    "program": "blastp",
    "query_sequence_type": "protein",
    "query_accession": "",
    "query_length": 30,
    "top_hit": {
        "accession": "P01316",
        "description": "Insulin",
        "evalue": 1.9e-17,
        "evalue_raw": "1.9e-17",
        "identity_pct": 100.0,
        "bit_score": 69.3,
        "alignment_length": 30,
    },
    "hits": [
        {
            "accession": "P01316",
            "description": "Insulin",
            "evalue": "1.9e-17",
            "identity_pct": 100.0,
            "bit_score": 69.3,
            "alignment_length": 30,
        },
        {
            "accession": "P01308",
            "description": "Insulin",
            "evalue": "3.2e-17",
            "identity_pct": 100.0,
            "bit_score": 68.2,
            "alignment_length": 30,
        },
    ],
}


def test_blast_engine_registered():
    assert "blast" in ENGINES
    assert get_engine("blast") is ENGINES["blast"]
    assert get_engine("nope") is None


def test_parse_maps_canonical_result():
    eng = get_engine("blast")
    res = eng.parse(CANONICAL)
    assert isinstance(res, EngineResult)
    assert res.engine == "blast"
    assert res.tool == "BLAST"
    assert res.database == "swissprot"
    assert res.statistics["count"] == 2
    assert res.statistics["top_hit_identity"] == 100.0
    assert res.evidence["top_hit"]["accession"] == "P01316"
    assert len(res.evidence["hits"]) == 2
    assert res.created_at


def test_parse_rejects_non_canonical():
    eng = get_engine("blast")
    try:
        eng.parse({"nonsense": True})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_validate_accepts_good_result():
    eng = get_engine("blast")
    report = eng.validate(eng.parse(CANONICAL))
    assert isinstance(report, ValidationReport)
    assert report.valid


def test_validate_flags_bad_identity_and_missing_top_hit():
    eng = get_engine("blast")
    bad = dict(CANONICAL)
    bad["top_hit"] = dict(CANONICAL["top_hit"], identity_pct=150.0)
    assert not eng.validate(eng.parse(bad)).valid

    missing = {"count": 3, "database": "swissprot", "program": "blastp", "query_length": 30, "hits": []}
    report = eng.validate(eng.parse(missing))
    # count=3 > 0 with no top_hit must fail
    names = [c["name"] for c in report.checks]
    assert "top_hit_present" in names
    assert not report.valid


def test_export_json_roundtrip():
    eng = get_engine("blast")
    out = eng.export(eng.parse(CANONICAL), "json")
    import json

    parsed = json.loads(out)
    assert parsed["engine"] == "blast"
    assert parsed["statistics"]["count"] == 2


def test_export_csv_rows():
    eng = get_engine("blast")
    out = eng.export(eng.parse(CANONICAL), "csv")
    lines = out.strip().splitlines()
    assert lines[0].startswith("accession,description")
    assert lines[1].startswith("P01316,Insulin")
    assert len(lines) == 3


def test_export_rejects_unknown_format():
    eng = get_engine("blast")
    try:
        eng.export(eng.parse(CANONICAL), "docx")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_figure_svg():
    eng = get_engine("blast")
    svg = eng.figure(eng.parse(CANONICAL))
    assert svg.startswith("<?xml")
    assert "<svg" in svg
    assert "P01316" in svg
    assert "width=" in svg


def test_describe_has_scientific_contract():
    eng = get_engine("blast")
    d = eng.describe()
    assert d["name"] == "blast"
    assert "Altschul" in d["citations"][0]
    assert "INSULIN_SWISSPROT_TOP_HIT" in d["benchmarks"]
    assert {"json", "csv"} <= set(d["export_formats"])
    assert "svg" in d["figure_formats"]