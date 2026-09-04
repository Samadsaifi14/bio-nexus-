"""Unit tests for the benchmark runner's metric comparison and extraction.

These are pure functions (no DB), so they run without mocking Supabase.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.benchmarks import _metric_value, compare_metric


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


def test_metric_value_missing_section():
    assert _metric_value({}, "blast", "top_hit_accession") is None
    assert _metric_value({"blast": {}}, "blast", "top_hit_identity") is None