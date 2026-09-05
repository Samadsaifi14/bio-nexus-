"""NGS Engine (Component 11) unit tests — no DB, no binary deps."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, ngs_engine

PIPELINE_OK = {
    "assay": "WGS",
    "reference": "grch38",
    "reads_analyzed": 400,
    "all_records_processed": True,
    "synthetic_reference": True,
    "validation": {"passed": True, "warnings": []},
    "stages": {
        "raw_read_qc": {"q30_pct": 92.5, "gc_pct": 41.8},
        "alignment_qc": {"mapping_rate": 0.994},
        "variant_calling": {"variants": 6, "snps": 4, "indels": 2},
    },
}


def test_registered_in_registry():
    assert "ngs" in ENGINES


def test_parse_extracts_statistics():
    result = ngs_engine.parse(PIPELINE_OK)
    s = result.statistics
    assert s["reads_analyzed"] == 400
    assert abs(s["q30_pct"] - 92.5) < 0.01
    assert abs(s["mapping_rate"] - 0.994) < 1e-6
    assert s["variant_count"] == 6
    assert s["all_records_processed"] is True


def test_validate_passes_good_pipeline():
    report = ngs_engine.validate(ngs_engine.parse(PIPELINE_OK))
    assert report.valid, [c for c in report.checks if not c["passed"]]


def test_validate_fails_q30_out_of_range():
    raw = dict(PIPELINE_OK)
    raw["stages"] = {"raw_read_qc": {"q30_pct": 130.0, "gc_pct": 40.0},
                     "alignment_qc": {"mapping_rate": 0.9},
                     "variant_calling": {"variants": 1}}
    report = ngs_engine.validate(ngs_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "q30_bounded" in names


def test_validate_rejects_negative_variants():
    raw = dict(PIPELINE_OK)
    raw["stages"] = {"variant_calling": {"variants": -3}}
    report = ngs_engine.validate(ngs_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "variant_count_nonnegative" in names


def test_reads_present_required():
    raw = dict(PIPELINE_OK)
    raw["reads_analyzed"] = 0
    report = ngs_engine.validate(ngs_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "reads_present" in names


def test_export_csv_and_json():
    result = ngs_engine.parse(PIPELINE_OK)
    csv = ngs_engine.export(result, "csv")
    assert csv.startswith("metric,value")
    assert "q30_pct,92.5" in csv
    js = ngs_engine.export(result, "json")
    assert '"engine": "ngs"' in js


def test_figure_svg_valid():
    svg = ngs_engine.figure(ngs_engine.parse(PIPELINE_OK))
    assert svg.count("<svg") == svg.count("</svg>")
    assert "NGS QC summary" in svg


def test_validate_empty_degrades():
    report = ngs_engine.validate(ngs_engine.parse(None))
    assert not report.valid