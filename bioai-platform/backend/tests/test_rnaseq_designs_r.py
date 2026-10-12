"""Executed R controls for paired, blocked and partially confounded designs."""
import csv
import json
import os
import shutil

import numpy as np
import pytest

from app.rnaseq.expression import ExpressionParameters, RnaSeqExpressionError, _run_r

pytestmark = pytest.mark.skipif(not shutil.which(os.environ.get("BIONEXUS_RSCRIPT", "Rscript")), reason="R scientific runtime is absent")


def evaluate(tmp_path, units, batches, covariates):
    conditions = ["a"] * 4 + ["b"] * 4
    values = np.random.default_rng(42).negative_binomial(12, .12, size=(160, 8)) + 1
    counts = tmp_path / "counts.tsv"
    with counts.open("w") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["gene", *[f"s{i}" for i in range(8)]])
        writer.writerows([f"gene{i}", *row] for i, row in enumerate(values))
    metadata = tmp_path / "metadata.tsv"
    with metadata.open("w") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["sample", "condition", "experimental_unit", "batch"])
        writer.writerows([f"s{i}", conditions[i], units[i], batches[i]] for i in range(8))
    out = tmp_path / "results"; out.mkdir()
    summary = _run_r(counts, metadata, out, ExpressionParameters(reference_level="a", test_level="b", covariates=tuple(covariates), min_samples=4), stage="qc", checkpoint_path=tmp_path / "qc.rds")
    assert summary["inference_performed"] is False
    return json.loads((out / "design_audit.json").read_text())


@pytest.mark.parametrize("batches,covariates", [
    (["x", "y", "x", "y"] * 2, ["batch"]),
    (["x", "x", "x", "y", "x", "y", "y", "y"], ["batch"]),
    (["x", "x", "y", "y", "z", "z", "w", "w"], []),
])
def test_blocked_partial_and_recorded_nested_designs(tmp_path, batches, covariates):
    audit = evaluate(tmp_path, [f"u{i}" for i in range(8)], batches, covariates)
    assert audit["design_full_rank"] is True
    if not covariates:
        assert "batch" in audit["confounded_columns"]
        assert any("condition-only" in message for message in audit["warnings"])


def test_numeric_paired_subject_ids_are_categorical(tmp_path):
    audit = evaluate(tmp_path, [1, 2, 3, 4] * 2, ["x"] * 8, ["experimental_unit"])
    assert audit["experimental_unit_status"] == "REPEATED_AND_MODELLED"
    assert audit["design_columns"] == 5


def test_requested_perfectly_confounded_batch_fails_rank(tmp_path):
    with pytest.raises(RnaSeqExpressionError, match="not full rank"):
        evaluate(tmp_path, [f"u{i}" for i in range(8)], ["x"] * 4 + ["y"] * 4, ["batch"])


def test_repeated_units_cannot_be_ignored(tmp_path):
    with pytest.raises(RnaSeqExpressionError, match="absent from the model"):
        evaluate(tmp_path, [1, 2, 3, 4] * 2, ["x"] * 8, [])


def test_within_condition_repeats_need_aggregation_or_correlation_model(tmp_path):
    with pytest.raises(RnaSeqExpressionError, match="Repeated observations"):
        evaluate(tmp_path, [1, 1, 2, 2] * 2, ["x"] * 8, ["experimental_unit"])
