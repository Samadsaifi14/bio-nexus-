"""Statistical validation helpers for benchmark and comparison studies.

These routines are designed for performance reporting rather than biological
inference. They expose sample sizes, uncertainty, effect sizes, sensitivity,
cross-validation summaries and failure modes without silently inventing exact
p-values when an exact distribution is unavailable.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from typing import Callable, Iterable

from app.engines.stats_engine import bootstrap_ci, cohens_d


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / len(vals) if vals else 0.0


def bootstrap_metric(
    values: list[float],
    confidence: float = 0.95,
    iterations: int = 5000,
    seed: int = 0,
) -> dict:
    """Bootstrap a scalar benchmark metric with deterministic resampling."""
    result = bootstrap_ci(values, confidence=confidence, n_boot=iterations, seed=seed)
    return {
        **result,
        "reporting_role": "performance_uncertainty",
        "interpretation_boundary": "This interval quantifies resampling uncertainty for the supplied observations only.",
    }


def paired_effect_size(reference: list[float], candidate: list[float]) -> dict:
    n = min(len(reference), len(candidate))
    if n == 0:
        return {"n": 0, "mean_difference": None, "cohens_d": None}
    ref = [float(x) for x in reference[:n]]
    cand = [float(x) for x in candidate[:n]]
    diffs = [c - r for r, c in zip(ref, cand)]
    return {
        "n": n,
        "mean_reference": _mean(ref),
        "mean_candidate": _mean(cand),
        "mean_difference": _mean(diffs),
        "cohens_d_unpaired_approximation": cohens_d(cand, ref),
        "direction": "candidate_minus_reference",
    }


def sensitivity_analysis(
    parameter_values: list[float],
    metric_values: list[float],
    baseline_index: int = 0,
) -> dict:
    """Summarise how a reported metric changes across a declared parameter sweep."""
    n = min(len(parameter_values), len(metric_values))
    if n == 0:
        return {"n": 0, "rows": [], "max_absolute_change": None}
    params = [float(x) for x in parameter_values[:n]]
    metrics = [float(x) for x in metric_values[:n]]
    baseline_index = min(max(int(baseline_index), 0), n - 1)
    baseline = metrics[baseline_index]
    rows = []
    for p, m in zip(params, metrics):
        rows.append({
            "parameter": p,
            "metric": m,
            "absolute_change_from_baseline": m - baseline,
            "relative_change_from_baseline": None if baseline == 0 else (m - baseline) / abs(baseline),
        })
    return {
        "n": n,
        "baseline_index": baseline_index,
        "baseline_parameter": params[baseline_index],
        "baseline_metric": baseline,
        "rows": rows,
        "max_absolute_change": max(abs(r["absolute_change_from_baseline"]) for r in rows),
        "interpretation_boundary": "Sensitivity describes the evaluated parameter grid; it does not prove robustness outside that grid.",
    }


def kfold_indices(n: int, folds: int = 5, seed: int = 0) -> list[dict]:
    n = max(0, int(n))
    folds = max(2, min(int(folds), n)) if n >= 2 else 0
    if folds == 0:
        return []
    indices = list(range(n))
    random.Random(seed).shuffle(indices)
    buckets = [indices[i::folds] for i in range(folds)]
    out = []
    for i, test in enumerate(buckets):
        test_set = set(test)
        train = [j for j in indices if j not in test_set]
        out.append({"fold": i + 1, "train_indices": train, "test_indices": test})
    return out


def cross_validation_summary(scores: list[float], folds: int | None = None) -> dict:
    vals = [float(x) for x in scores]
    if not vals:
        return {"folds": 0, "scores": [], "mean": None, "sd": None, "min": None, "max": None}
    mean = _mean(vals)
    sd = math.sqrt(sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)) if len(vals) > 1 else 0.0
    return {
        "folds": int(folds or len(vals)),
        "scores": vals,
        "mean": mean,
        "sd": sd,
        "min": min(vals),
        "max": max(vals),
        "range": max(vals) - min(vals),
    }


def failure_analysis(cases: list[dict]) -> dict:
    """Aggregate benchmark failures without hiding them from the final report."""
    total = len(cases)
    failed = [case for case in cases if not bool(case.get("passed", case.get("pass", False)))]
    reasons = Counter(str(case.get("failure_reason") or case.get("reason") or "unspecified") for case in failed)
    domains = Counter(str(case.get("domain") or "unspecified") for case in failed)
    return {
        "total_cases": total,
        "failed_cases": len(failed),
        "failure_rate": (len(failed) / total) if total else 0.0,
        "failure_reasons": dict(reasons.most_common()),
        "failure_domains": dict(domains.most_common()),
        "failed_case_ids": [str(c.get("id") or c.get("benchmark_id") or i) for i, c in enumerate(failed)],
        "policy": "Failed cases remain visible and are not excluded from aggregate reporting unless a predeclared exclusion rule exists.",
    }


def comparison_report(
    candidate: list[float],
    reference: list[float],
    confidence: float = 0.95,
    iterations: int = 5000,
    seed: int = 0,
) -> dict:
    """One object suitable for a benchmark figure/report panel."""
    n = min(len(candidate), len(reference))
    cand = [float(x) for x in candidate[:n]]
    ref = [float(x) for x in reference[:n]]
    diffs = [c - r for c, r in zip(cand, ref)]
    return {
        "n": n,
        "candidate": bootstrap_metric(cand, confidence, iterations, seed),
        "reference": bootstrap_metric(ref, confidence, iterations, seed + 1),
        "difference": bootstrap_metric(diffs, confidence, iterations, seed + 2),
        "effect_size": paired_effect_size(ref, cand),
        "statistical_significance": {
            "p_value": None,
            "status": "not_computed",
            "reason": "Use a predeclared validated paired inferential test appropriate to the benchmark design before reporting significance."
        },
    }
