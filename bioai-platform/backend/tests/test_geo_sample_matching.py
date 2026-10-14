"""Identity matching must be unique, delimited and metadata-order invariant."""
import asyncio

import pytest

from app.rnaseq.geo_counts import _match_column, parse_matrix
from app.routers import geo_search


SAMPLES = [
    {"accession": "GSM1", "title": "control GZ10001"},
    {"accession": "GSM10", "title": "control GZ100010"},
    {"accession": "GSM2", "title": "treated GZ10002"},
    {"accession": "GSM3", "title": "treated GZ10003"},
]


@pytest.mark.parametrize("column,expected", [
    ("GSM10", "GSM10"), ("batch_GSM10_counts", "GSM10"),
    ("gsm1.bam", "GSM1"), ("GSM100", None), ("xGSM1", None),
    ("GSM1x", None), ("GSM1_GSM10", None),
    ("batch_GZ100010_counts", "GSM10"), ("GZ1000100", None),
    ("xGZ10001", None), ("control GZ10001", "GSM1"),
    ("GSM10_GZ10001", "GSM10"), ("GSM999_GZ10001", None),
    ("unknown", None),
])
def test_delimited_identifiers_and_priority(column, expected):
    assert _match_column(column, SAMPLES) == expected
    assert _match_column(column, list(reversed(SAMPLES))) == expected


def test_duplicate_lab_identifiers_require_manual_mapping():
    samples = [{"accession": "GSM1", "title": "sample GZ10001"},
               {"accession": "GSM2", "title": "sample GZ10001"}]
    assert _match_column("batch_GZ10001", samples) is None
    assert _match_column("sample GZ10001", samples) is None
    assert _match_column("GSM2_GZ10001", samples) == "GSM2"


def matrix(columns, samples=SAMPLES):
    payload = ("gene," + ",".join(columns) + "\ng1,1,2,3,4\ng2,5,6,7,8\n").encode()
    return parse_matrix(payload, "raw_counts.csv", samples)


def test_reordered_metadata_does_not_reorder_count_columns():
    columns = ["batch_GSM10", "GSM3", "GSM1", "GSM2"]
    normal = matrix(columns)
    reordered = matrix(columns, list(reversed(SAMPLES)))
    assert normal == reordered
    assert normal["matched_samples"] == ["GSM10", "GSM3", "GSM1", "GSM2"]
    assert normal["rows"][0] == ["g1", "1", "2", "3", "4"]


def test_duplicate_column_matches_leave_both_unassigned():
    parsed = matrix(["GSM1", "batch_GSM1", "GSM2", "unmatched"])
    assert parsed["matched_samples"] == [None, None, "GSM2", None]
    assert [item["status"] for item in parsed["sample_mapping"]] == [
        "duplicate_sample", "duplicate_sample", "matched", "unmatched"]
    assert parsed["sample_mapping"][0]["candidates"] == ["GSM1"]


def test_ambiguous_preview_still_exposes_manual_choices(monkeypatch):
    samples = [{**sample, "title": "shared GZ10001"} for sample in SAMPLES]
    parsed = matrix(["GZ10001", "GSM10", "GSM2", "unknown"], samples)

    async def fake_series(client, accession):
        return {"accession": accession, "samples": samples, "design": "two groups"}

    async def fake_matrix(client, series, filename):
        return parsed, "https://ftp.ncbi.nlm.nih.gov/raw_counts.csv"

    monkeypatch.setattr(geo_search, "fetch_series", fake_series)
    monkeypatch.setattr(geo_search, "fetch_matrix", fake_matrix)
    result = asyncio.run(geo_search.preview_geo_matrix(
        geo_search.MatrixSelection(accession="GSE336901", filename="raw_counts.csv")))
    assert result["columns"][0]["gsm"] is None
    assert result["columns"][0]["mapping"]["status"] == "ambiguous"
    assert result["columns"][0]["mapping"]["candidates"] == ["GSM1", "GSM10", "GSM2", "GSM3"]
    assert [{key: row[key] for key in ("accession", "title")} for row in result["samples"]] == samples
    assert all(row["suggested_condition"] is None for row in result["samples"])
    assert result["columns"][1]["gsm"] == "GSM10"
