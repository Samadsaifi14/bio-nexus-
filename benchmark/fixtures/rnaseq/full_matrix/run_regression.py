#!/usr/bin/env python3
"""Retained complete-matrix parity control, not biological/origin validation."""
import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "bioai-platform/backend"))
from app.rnaseq.expression import ExpressionParameters, _run_r, validate_artifacts


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_tables(reference, actual, key, fields, tolerance=1e-7):
    def read(path):
        with path.open() as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        mapped = {row[key]: row for row in rows}
        if len(mapped) != len(rows):
            raise AssertionError("Duplicate table keys: " + str(path))
        return mapped
    expected, observed = read(reference), read(actual)
    assert set(expected) == set(observed), f"Row identity mismatch: {actual.name}"
    maximum = 0.0
    for name in expected:
        for field in fields:
            left, right = expected[name][field], observed[name][field]
            if left in {"", "NA"} or right in {"", "NA"}:
                assert left in {"", "NA"} and right in {"", "NA"}, (name, field)
            elif left in {"TRUE", "FALSE"}:
                assert left == right, (name, field)
            else:
                left, right = float(left), float(right)
                assert math.isfinite(left) and math.isfinite(right), (name, field)
                maximum = max(maximum, abs(left - right))
                assert math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance), (actual.name, name, field, left, right)
    return {"rows": len(expected), "fields": fields, "maximum_absolute_difference": maximum, "tolerance": tolerance}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=ROOT / "benchmark/results/rnaseq/complete-matrix")
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = args.outdir / run_id
    out.mkdir(parents=True, exist_ok=False)
    record = {"run_id": run_id, "status": "NOT_EXECUTED", "evidence_class": "numerical_regression",
              "biological_validation": False, "raw_count_origin_independently_verified": False,
              "fixture_sha256": {name: digest(HERE / name) for name in ("counts.tsv", "metadata.tsv", "runtime-lock.json", "independent_reference.R")}}
    try:
        rscript = shutil.which(os.environ.get("BIONEXUS_RSCRIPT", "Rscript"))
        if not rscript:
            record["reason"] = "Rscript is unavailable; no numerical execution or parity claim"
            return 2
        lock = json.loads((HERE / "runtime-lock.json").read_text())
        code = 'library(jsonlite); cat(toJSON(list(R=as.character(getRversion()), packages=list(DESeq2=as.character(packageVersion("DESeq2")),ggplot2=as.character(packageVersion("ggplot2")))),auto_unbox=TRUE))'
        probe = subprocess.run([rscript, "-e", code], capture_output=True, text=True, timeout=60, check=True)
        versions = json.loads(probe.stdout)
        record["runtime_versions"] = versions
        if versions["R"] != lock["R"] or versions["packages"] != lock["packages"]:
            record["status"] = "BLOCKED_RUNTIME_MISMATCH"
            return 2
        record["status"] = "RUNNING"
        for name in ("counts.tsv", "metadata.tsv", "runtime-lock.json"):
            shutil.copyfile(HERE / name, out / name)
        qc, infer, reference = (out / name for name in ("qc", "infer", "reference"))
        for folder in (qc, infer, reference):
            folder.mkdir()
        checkpoint = out / "qc_checkpoint.rds"
        params = ExpressionParameters(reference_level="healthy", test_level="SALS", min_samples=8)
        summary = _run_r(out / "counts.tsv", out / "metadata.tsv", qc, params, stage="qc", checkpoint_path=checkpoint)
        validate_artifacts(qc, summary, "qc")
        assert summary["inference_performed"] is False
        summary = _run_r(out / "counts.tsv", out / "metadata.tsv", infer, params, stage="infer", checkpoint_path=checkpoint)
        validate_artifacts(infer, summary, "infer")
        assert summary["genes_input"] == 22085 and summary["samples"] == 18
        direct = subprocess.run([rscript, str(HERE / "independent_reference.R"), str(out / "counts.tsv"), str(out / "metadata.tsv"), str(reference)], capture_output=True, text=True, timeout=900)
        (out / "reference_stdout.log").write_text(direct.stdout)
        (out / "reference_stderr.log").write_text(direct.stderr)
        assert direct.returncode == 0, direct.stderr[-1000:]
        samples = list(csv.reader((out / "counts.tsv").open(), delimiter="\t"))[0][1:]
        specifications = [
            ("deseq2_all_results.tsv", "gene", ["baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj", "significant"], infer),
            ("size_factors.tsv", "sample", ["size_factor"], qc),
            ("normalized_counts.tsv", "gene", samples, qc),
            ("pca_coordinates.tsv", "sample", ["PC1", "PC2"], qc),
            ("sample_distance_matrix.tsv", "sample", samples, qc),
            ("volcano_plot_data.tsv", "gene", ["log2FoldChange", "padj", "minus_log10_padj", "significant"], infer),
        ]
        if (reference / "heatmap_matrix_zscore.tsv").exists():
            specifications.append(("heatmap_matrix_zscore.tsv", "gene", samples, infer))
        record["comparisons"] = {name: compare_tables(reference / name, folder / name, key, fields) for name, key, fields, folder in specifications}
        record["status"] = "PASSED"
        return 0
    except Exception as exc:
        record.update(status="FAILED", reason=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        record["code_sha256"] = digest(ROOT / "bioai-platform/backend/app/rnaseq/deseq2_analysis.R")
        record["artifact_sha256"] = {str(path.relative_to(out)): digest(path) for path in sorted(out.rglob("*")) if path.is_file()}
        (out / "report.json").write_text(json.dumps(record, indent=2) + "\n")
        (args.outdir / "latest.json").write_text(json.dumps(record, indent=2) + "\n")
        print(record["status"])


if __name__ == "__main__":
    raise SystemExit(main())
