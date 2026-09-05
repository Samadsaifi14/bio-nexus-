"""Unit tests for the benchmark runner's metric comparison and extraction.

These are pure functions (no DB), so they run without mocking Supabase.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.benchmarks import (
    _benchmark_row,
    _metric_value,
    compare_metric,
    load_benchmark_files,
)


def test_compare_metric_numeric_tolerance():
    assert compare_metric(100.0, 100.0, 1.0)
    assert compare_metric(99.5, 100.0, 1.0)
    assert not compare_metric(98.0, 100.0, 1.0)


def test_compare_metric_exact_string():
    assert compare_metric("P01308", "P01308", 0)
    assert not compare_metric("P01316", "P01308", 0)


def test_compare_metric_contains_matcher():
    assert compare_metric("Insulin", {"contains": "Insulin"}, 0)
    assert compare_metric("Insulin [Elephas maximus]", {"contains": "Insulin"}, 0)
    assert not compare_metric("Cellular tumor antigen p53", {"contains": "Insulin"}, 0)


def test_compare_metric_min_matcher():
    assert compare_metric(6, {"min": 2}, 0)
    assert compare_metric(2, {"min": 2}, 0)
    assert not compare_metric(1, {"min": 2}, 0)
    assert not compare_metric("many", {"min": 2}, 0)
    assert not compare_metric(None, {"min": 2}, 0)


def test_compare_metric_max_matcher():
    assert compare_metric(0.95, {"max": 1.0}, 0)
    assert not compare_metric(1.05, {"max": 1.0}, 0)


def test_metric_value_full_name_contains():
    ctx = {"uniprot": {"accession": "Q9TTA1", "full_name": "Cellular tumor antigen p53"}}
    got = _metric_value(ctx, "uniprot", "full_name")
    assert got == "Cellular tumor antigen p53"
    assert compare_metric(got, {"contains": "p53"}, 0)
    assert not compare_metric(got, {"contains": "Insulin"}, 0)


def test_compare_metric_contains_requires_string():
    assert not compare_metric(100.0, {"contains": "Insulin"}, 0)
    assert not compare_metric(None, {"contains": "Insulin"}, 0)


def test_metric_value_top_hit_fields():
    context = {
        "blast": {
            "count": 10,
            "top_hit": {
                "accession": "P01316",
                "description": "Insulin",
                "identity_pct": 100.0,
            },
        }
    }
    assert _metric_value(context, "blast", "top_hit_accession") == "P01316"
    assert _metric_value(context, "blast", "top_hit_description") == "Insulin"
    assert _metric_value(context, "blast", "top_hit_identity") == 100.0
    assert _metric_value(context, "blast", "hit_count") == 10


def test_metric_value_domain_count():
    ctx = {"domains": {"domains": [{"accession": "IPR001234", "start": 1, "end": 10}]}}
    assert _metric_value(ctx, "domains", "domain_count") == 1
    assert _metric_value({}, "domains", "domain_count") is None


def test_metric_value_missing_section():
    assert _metric_value({}, "blast", "top_hit_accession") is None
    assert _metric_value({"blast": {}}, "blast", "top_hit_identity") is None


def test_benchmark_row_includes_depth_fields():
    rec = {
        "category": "domain_annotation",
        "name": "DOMAINS_ANNOTATED",
        "section": "domains",
        "difficulty": "medium",
        "version": 3,
    }
    row = _benchmark_row(rec)
    assert row["difficulty"] == "medium"
    assert row["registry_version"] == 3
    assert row["section"] == "domains"


def test_benchmark_row_defaults():
    rec = {"category": "x", "name": "Y"}
    row = _benchmark_row(rec, omit_section=True)
    assert row["difficulty"] == "easy"
    assert row["registry_version"] == 1
    assert "section" not in row


def test_benchmark_row_omit_depth():
    rec = {"category": "x", "name": "Y", "difficulty": "hard", "version": 4}
    row = _benchmark_row(rec, omit_depth=True)
    assert "difficulty" not in row
    assert "registry_version" not in row
    assert row["section"] == "blast"


def test_catalog_loads_with_depth_and_unique_names():
    records = load_benchmark_files()
    assert records, "catalog must not be empty"
    names = [r["name"] for r in records]
    assert len(names) == len(set(names)), "benchmark names must be unique"
    for rec in records:
        assert rec.get("expected_output"), rec["name"]
        assert rec.get("ground_truth"), rec["name"]
        assert rec.get("citation"), rec["name"]
        assert rec.get("difficulty") in {"easy", "medium", "hard"}, rec["name"]
        assert rec.get("version", 1) >= 1, rec["name"]
        assert rec.get("category"), rec["name"]