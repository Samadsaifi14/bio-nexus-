"""Unit tests for the interpret engine — honest-AI scientific object.

No network, no DB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, get_engine

REPORT = {"interpretation": "TP53 (Q9TTA1) is a tumor suppressor. The top swissprot hit is p53; domain analysis shows the p53 DNA-binding domain (PF00870). Confidence: identified."}
BANNER = {"interpretation": "AI interpretation unavailable: no LLM API keys configured"}


def test_interpret_engine_registered():
    assert "interpret" in ENGINES
    assert get_engine("interpret") is ENGINES["interpret"]


def test_parse_maps_report():
    eng = get_engine("interpret")
    res = eng.parse(REPORT)
    assert res.engine == "interpret"
    assert res.statistics["is_report"] is True
    assert res.statistics["honest_banner"] is False
    assert res.statistics["word_count"] > 10


def test_parse_detects_banner():
    eng = get_engine("interpret")
    res = eng.parse(BANNER)
    assert res.statistics["honest_banner"] is True
    assert res.statistics["is_report"] is False


def test_parse_rejects_non_canonical():
    eng = get_engine("interpret")
    for bad in ({"nonsense": 1}, {"interpretation": 42}):
        try:
            eng.parse(bad)
            assert False, f"expected ValueError for {bad}"
        except ValueError:
            pass


def test_validate_report_ok():
    eng = get_engine("interpret")
    assert eng.validate(eng.parse(REPORT)).valid
    assert not any(c["name"] == "report_not_placeholder" and not c["passed"] for c in eng.validate(eng.parse(REPORT)).checks)


def test_validate_banner_is_honest_ok():
    eng = get_engine("interpret")
    report = eng.validate(eng.parse(BANNER))
    assert report.valid
    assert any(c["name"] == "honest_failure_banner" and c["passed"] for c in report.checks)


def test_validate_empty_report_fails():
    eng = get_engine("interpret")
    report = eng.validate(eng.parse({"interpretation": ""}))
    assert not report.valid
    assert any(c["name"] == "not_fabricated_empty" and not c["passed"] for c in report.checks)


def test_export_txt():
    eng = get_engine("interpret")
    assert eng.export(eng.parse(REPORT), "txt") == REPORT["interpretation"]
    out = eng.export(eng.parse(REPORT), "json")
    assert '"interpretation"' in out


def test_figure_svg():
    eng = get_engine("interpret")
    svg = eng.figure(eng.parse(REPORT))
    assert svg.startswith("<?xml")
    assert "AI interpretation" in svg
    banner_svg = eng.figure(eng.parse(BANNER))
    assert "Availability banner" in banner_svg


def test_describe_contract():
    eng = get_engine("interpret")
    d = eng.describe()
    assert "honest" in d["citations"][0].lower()
    assert "txt" in d["export_formats"]
    assert d["databases"] == []