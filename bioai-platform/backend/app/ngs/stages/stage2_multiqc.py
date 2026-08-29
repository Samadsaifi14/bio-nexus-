"""
Stage 2 — MultiQC: cross-sample view + anomaly detection (blueprint Stage 2).

A scientist should not have to eyeball 24 FastQC reports to spot the one bad sample.
This stage ingests the per-sample raw QC results and:
  * shakes out the cross-sample table (Q30, GC, adapter, duplication, read count, ...)
  * computes a robust cohort baseline (median + MAD) per metric
  * flags any sample that deviates markedly from the cohort as an ANOMALY

Blueprint example honored: samples at Q30 94/93/91/61 -> the 61 is flagged automatically.

The stage runs per-cohort (the set of samples in the run), not per sample.
"""

from __future__ import annotations

import statistics
from typing import Any, Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule

# Metrics scanned across samples; each maps to a raw_qc key + a "higher is better" flag.
_SAMPLED_METRICS = [
    ("q30", "q30_percent", True),
    ("mean_quality", "mean_quality", True),
    ("gc", "gc_percent", False),        # anomaly = deviation from median (either direction)
    ("adapter", "adapter_percent", False),
    ("duplication", "duplication_percent", False),
    ("read_count", "total_reads", False),
]


def _median_mad(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    devs = [abs(v - med) for v in values]
    mad = statistics.median(devs) if len(devs) > 1 else 0.0
    return med, mad


def cross_sample_report(per_sample: dict[str, dict]) -> dict:
    """per_sample: {sample_id: raw_qc_dict}. Returns a MultiQC-style report with anomalies."""
    samples = list(per_sample.keys())
    # Build per-metric value vectors in sample order.
    vectors: dict[str, list[Optional[float]]] = {m[0]: [] for m in _SAMPLED_METRICS}
    for sid in samples:
        qc = per_sample.get(sid) or {}
        for metric, key, _ in _SAMPLED_METRICS:
            v = qc.get(key)
            vectors[metric].append(v if isinstance(v, (int, float)) else None)

    anomalies: list[dict] = []
    summary_rows: dict[str, dict] = {}

    for metric, key, higher_is_better in _SAMPLED_METRICS:
        present = [v for v in vectors[metric] if v is not None]
        if len(present) < 3:
            summary_rows[metric] = {"n": len(present), "note": "insufficient samples for cohort stats"}
            continue
        med, mad = _median_mad(present)
        # Robust Z-like deviation: (v - med) / (1.4826 * mad + tiny)
        scale = 1.4826 * mad + 1e-9
        row = {"median": round(med, 2), "mad": round(mad, 2), "outliers": []}
        for idx, v in enumerate(vectors[metric]):
            if v is None:
                continue
            z = (v - med) / scale
            # Flag if beyond ~3 robust-SD. For higher-is-better, only flag on the low side.
            if abs(z) >= 3.0:
                direction = "low" if (higher_is_better and z < 0) else (
                    "high" if (not higher_is_better and z > 3) else "both"
                )
                row["outliers"].append({
                    "sample": samples[idx],
                    "value": round(v, 2),
                    "z": round(z, 2),
                    "direction": direction,
                })
                anomalies.append({
                    "sample": samples[idx],
                    "metric": metric,
                    "value": round(v, 2),
                    "median": round(med, 2),
                    "z": round(z, 2),
                    "direction": direction,
                })
        summary_rows[metric] = row

    return {
        "samples": samples,
        "n_samples": len(samples),
        "metrics": summary_rows,
        "anomalies": anomalies,
        "cross_sample_table": {
            "samples": samples,
            "columns": [m[0] for m in _SAMPLED_METRICS],
            "rows": {
                sid: {m[0]: per_sample[sid].get(m[1]) for m in _SAMPLED_METRICS}
                for sid in samples
            },
        },
    }


def _stage2_run(sample: dict, state: dict) -> tuple[dict, dict]:
    """Stage 2 consumes the per-sample raw QC accumulated in state by earlier Stage 1 runs."""
    per_sample = state.get("raw_qc") or {}
    if not per_sample:
        # Allow direct invocation with a `cohort` key.
        per_sample = sample.get("cohort") or {}
    report = cross_sample_report(per_sample)
    anomaly_ratio = (len(report["anomalies"]) / len(per_sample) * 100.0) if per_sample else 0.0
    state.setdefault("multiqc", {})["report"] = report
    return report, {
        "anomaly_ratio": anomaly_ratio,
        "cohort_coverage": 100.0 if per_sample else 0.0,
    }


def stage2_contract() -> StageContract:
    return StageContract(
        step="multiqc",
        tool="platform-multiqc",
        version="0.1.0",
        inputs=["raw_qc_reports"],
        outputs=["cohort_anomaly_report"],
        rules=[
            ThresholdRule(name="anomaly_ratio", metric="anomaly_ratio",
                          evaluate=lambda v: _anomaly_rule(v)),
            ThresholdRule(name="cohort_coverage", metric="cohort_coverage",
                          evaluate=lambda v: QcStatus.PASS if v >= 100.0 else QcStatus.FAIL),
        ],
        fail_blocks=False,   # outliers are warnings/action items, not a hard stop
        run=_stage2_run,
    )


def _anomaly_rule(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v <= 5.0:
        return QcStatus.PASS
    if v <= 25.0:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_multiqc(per_sample: dict[str, dict]) -> dict:
    """Direct invocation: run cross-sample anomaly detection on a {sample: raw_qc} map."""
    contract = stage2_contract()
    data, metrics = _stage2_run({"cohort": per_sample}, {})
    qc = contract.evaluate(metrics, {"cohort": per_sample})
    return {
        "result": {"step": "multiqc", "qc": qc.to_dict(), "decision": qc.decision.value, "data": data},
        "summary": {"status": qc.status.value, "decision": qc.decision.value,
                    "anomalies": data.get("anomalies", [])},
    }
