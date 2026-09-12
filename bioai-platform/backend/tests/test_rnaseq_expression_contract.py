from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.rnaseq.expression import ExpressionParameters, R_SCRIPT, RnaSeqExpressionError


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "rnaseq"
COUNTS = DATA_DIR / "Cer_SALS_every100_validation_subset.tsv"
METADATA = DATA_DIR / "Cer_SALS_metadata.tsv"


def test_bundled_validation_subset_preserves_all_samples_and_raw_integers():
    with COUNTS.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        rows = list(reader)
    assert header[0] == "gene"
    assert len(header) == 19
    assert len(rows) == 221
    assert len(set(header[1:])) == 18
    assert all(len(row) == 19 for row in rows)
    assert all(cell.isdigit() for row in rows for cell in row[1:])


def test_bundled_metadata_matches_count_columns_exactly():
    with COUNTS.open("r", encoding="utf-8") as handle:
        count_samples = next(csv.reader(handle, delimiter="\t"))[1:]
    with METADATA.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["sample"] for row in rows] == count_samples
    assert sum(row["condition"] == "healthy" for row in rows) == 8
    assert sum(row["condition"] == "SALS" for row in rows) == 10


def test_expression_parameters_fail_closed_on_unsafe_design_names():
    with pytest.raises(RnaSeqExpressionError):
        ExpressionParameters(covariates=("batch + system('x')",)).validate()
    with pytest.raises(RnaSeqExpressionError):
        ExpressionParameters(reference_level="SALS", test_level="SALS").validate()


def test_r_script_contains_required_statistical_and_figure_stages():
    text = R_SCRIPT.read_text(encoding="utf-8")
    for token in (
        "DESeqDataSetFromMatrix",
        "estimateSizeFactors",
        "vst(dds, blind = TRUE)",
        "varianceStabilizingTransformation(dds, blind = TRUE)",
        "plotPCA",
        "DESeq(dds)",
        "results(dds",
        "lfcShrink",
        "ComplexHeatmap",
        "sample_distance_matrix.tsv",
        "deseq2_all_results.tsv",
        "heatmap_matrix_zscore.tsv",
    ):
        assert token in text
