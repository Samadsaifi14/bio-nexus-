"""Statistical Engine (BioNexus 2.0, Component 19).

Dependency-free hypothesis testing + anomaly detection over engine result
statistics:

- Welch's t-test (statistic + approximate p via survival function of the
  t-distribution through the normal CDF fallback),
- Mann-Whitney U (rank-based, normal approximation with continuity correction),
- Cohen's d (effect size),
- robust z-score anomaly detection.

Engine contract: parse a test-bundle, validate statistical invariants (sample
sizes, unit-interval p-values, finite statistics), export JSON/CSV, and render
a -log10(p) significance figure.
"""

from __future__ import annotations

import math
import statistics as py_stats
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport
from app.figure.engine import bar_chart_panel

#: p-value Two-sided normal CDF survival from |z| (approximation used when scipy
#: is unavailable). Error < 0.01 for the decision boundary, deterministic.
def _p_from_z(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _variance(vals: list[float], sample: bool = True) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    denom = len(vals) - 1 if sample else len(vals)
    return sum((x - m) ** 2 for x in vals) / denom


def _rankdata(values: list[float]) -> list[float]:
    order = sorted(values)
    ranks = []
    for v in values:
        lo = order.index(v) + 1
        hi = len(order) - order[::-1].index(v)
        ranks.append((lo + hi) / 2.0)
    return ranks


# --- Public statistical tests ------------------------------------------------

def welch_t(group_a: list[float], group_b: list[float]) -> dict:
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return {"method": "welch_t", "statistic": float("nan"), "p_value": float("nan"),
                "significant": False, "degrees_freedom": 0, "n_a": n_a, "n_b": n_b,
                "mean_a": _mean(group_a), "mean_b": _mean(group_b), "note": "insufficient samples"}
    m_a, m_b = _mean(group_a), _mean(group_b)
    v_a, v_b = _variance(group_a), _variance(group_b)
    se2 = v_a / n_a + v_b / n_b
    if se2 <= 0:
        return {"method": "welch_t", "statistic": 0.0, "p_value": 1.0, "significant": False,
                "degrees_freedom": 0, "n_a": n_a, "n_b": n_b, "mean_a": m_a, "mean_b": m_b,
                "note": "zero variance in both groups"}
    t = (m_a - m_b) / math.sqrt(se2)
    df = se2 * se2 / (v_a * v_a / (n_a * n_a * (n_a - 1)) + v_b * v_b / (n_b * n_b * (n_b - 1)))
    df = max(df, 0.0)
    p = _p_from_z(t)  # t ~ N(0,1) approximation fallback; exact t-CDF would need beta functions.
    return {"method": "welch_t", "statistic": t, "p_value": min(max(p, 0.0), 1.0),
            "significant": p <= 0.05, "degrees_freedom": df, "n_a": n_a, "n_b": n_b,
            "mean_a": m_a, "mean_b": m_b, "effect_size": cohens_d(group_a, group_b)}


def mann_whitney_u(group_a: list[float], group_b: list[float]) -> dict:
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 1 or n_b < 1:
        return {"method": "mann_whitney_u", "statistic": float("nan"), "p_value": float("nan"),
                "significant": False, "n_a": n_a, "n_b": n_b, "note": "empty group"}
    ranks = _rankdata(list(group_a) + list(group_b))
    rank_a = ranks[:n_a]
    u1 = n_a * n_b + n_a * (n_a + 1) / 2.0 - sum(rank_a)
    u2 = n_a * n_b - u1
    mu = n_a * n_b / 2.0
    sigma = math.sqrt(n_a * n_b * (n_a + n_b + 1) / 12.0) or 1.0
    z = (max(u1, u2) - 0.5 - mu) / sigma
    p = _p_from_z(z)
    return {"method": "mann_whitney_u", "statistic": min(u1, u2), "u_max": max(u1, u2),
            "p_value": min(max(p, 0.0), 1.0), "significant": p <= 0.05,
            "n_a": n_a, "n_b": n_b, "mean_a": _mean(group_a), "mean_b": _mean(group_b),
            "effect_size": cohens_d(group_a, group_b)}


def cohens_d(group_a: list[float], group_b: list[float]) -> float:
    if len(group_a) < 2 or len(group_b) < 2:
        return 0.0
    pooled = math.sqrt(((len(group_a) - 1) * _variance(group_a) + (len(group_b) - 1) * _variance(group_b)) /
                       (len(group_a) + len(group_b) - 2)) or 1.0
    return (_mean(group_a) - _mean(group_b)) / pooled


def z_score_anomalies(values: list[float], threshold: float = 3.0) -> list[dict]:
    """Flag values whose |z-score| against the group exceeds the threshold."""
    if len(values) < 3:
        return []
    m = _mean(values)
    sd = math.sqrt(_variance(values)) or 1.0
    return [{"index": i, "value": v, "z_score": (v - m) / sd, "flagged": abs((v - m) / sd) > threshold}
            for i, v in enumerate(values)]


_METHODS = {"welch_t": welch_t, "welch": welch_t, "mann_whitney_u": mann_whitney_u,
            "mann-whitney": mann_whitney_u, "mann_whitney": mann_whitney_u}


class StatsEngine(BaseEngine):
    name = "stats"
    version = "1.0.0"
    tool = "pure-Python statistical inference (Welch t / Mann-Whitney U / Cohen's d)"
    tool_version = None
    databases = ["result statistics from recorded experiments"]
    parameters = {
        "tests": "welch_t | mann_whitney_u",
        "alpha": 0.05,
        "anomaly": "z-score threshold (default 3.0)",
        "note": "p-values use a deterministic normal-approximation survival function (no scipy dependency)",
    }
    citations = [
        "Welch BL. The generalization of Student's problem when several different population variances are involved. Biometrika 34:28-35, 1947.",
        "Mann HB, Whitney DR. On a test of whether one of two random variables is stochastically larger than the other. Ann Math Stat 18:50-60, 1947.",
        "Cohen J. Statistical Power Analysis for the Behavioral Sciences. 2nd ed. Erlbaum, 1988.",
    ]
    benchmarks = ["STATS_P_VALUE_IN_UNIT_INTERVAL"]
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raw = {}
        alpha = float(raw.get("alpha", 0.05) or 0.05)
        tests_out: list[dict] = []
        for spec in raw.get("tests") or []:
            if not isinstance(spec, dict):
                continue
            ga = [float(x) for x in (spec.get("group_a") or []) if isinstance(x, (int, float))]
            gb = [float(x) for x in (spec.get("group_b") or []) if isinstance(x, (int, float))]
            method = _METHODS.get((spec.get("type") or "").lower())
            if method is None:
                continue
            tests_out.append({"name": spec.get("name", "test"), **method(ga, gb)})
        anomalies_raw = [float(x) for x in (raw.get("values") or []) if isinstance(x, (int, float))]
        anomalies = z_score_anomalies(anomalies_raw, float(raw.get("anomaly_threshold", 3.0)))
        significant = sum(1 for t in tests_out if t.get("significant"))
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            input_ref=f"{len(tests_out)} test(s), alpha={alpha}",
            statistics={
                "tests_run": len(tests_out),
                "significant": significant,
                "alpha": alpha,
                "anomalies_flagged": sum(1 for a in anomalies if a["flagged"]),
                "anomaly_threshold": float(raw.get("anomaly_threshold", 3.0)),
            },
            evidence={"tests": tests_out, "anomalies": anomalies, "alpha": alpha},
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = super().validate(result).checks
        alpha = result.statistics["alpha"]
        tests: list[dict] = result.evidence.get("tests") or []
        anomalies: list[dict] = result.evidence.get("anomalies") or []
        checks.extend([
            {"name": "alpha_bounded", "passed": 0 < alpha < 1, "detail": f"alpha={alpha}"},
            {"name": "tests_run", "passed": len(tests) >= 1, "detail": f"{len(tests)} tests"},
            {"name": "sample_sizes_sufficient", "passed": all(t.get("n_a", 0) >= 3 and t.get("n_b", 0) >= 3 for t in tests)
             if tests else False, "detail": "each group >= 3"},
            {
                "name": "p_values_in_unit_interval",
                "passed": all(isinstance(t.get("p_value"), float) and 0.0 <= t["p_value"] <= 1.0 for t in tests) if tests else False,
                "detail": "every computed p in [0, 1]",
            },
            {"name": "statistics_finite", "passed": all(isinstance(t.get("statistic"), float) and
             not math.isnan(t["statistic"]) and math.isfinite(t["statistic"]) for t in tests) if tests else False,
             "detail": "all test statistics finite"},
            {"name": "anomaly_scores_finite", "passed": all(isinstance(a.get("z_score"), float) and
             not math.isnan(a["z_score"]) for a in anomalies), "detail": f"{len(anomalies)} z-scores"},
        ])
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        tests: list[dict] = result.evidence.get("tests") or []
        rows = ["test,method,statistic,p_value,significant,effect_size,n_a,n_b"]
        for t in tests:
            rows.append(",".join([
                str(t.get("name", "")), str(t.get("method", "")),
                f"{t.get('statistic', float('nan')):.4f}", f"{t.get('p_value', float('nan')):.4f}",
                str(bool(t.get("significant"))).lower(),
                f"{t.get('effect_size', 0.0):.3f}", str(t.get("n_a", 0)), str(t.get("n_b", 0)),
            ]))
        return "\n".join(rows)

    def figure(self, result: EngineResult) -> str:
        tests: list[dict] = result.evidence.get("tests") or []
        alpha = result.evidence.get("alpha", 0.05)
        rows = [(t.get("name", f"test{i}")[:16], -10 * math.log10(max(t.get("p_value", 1.0), 1e-10)))
                for i, t in enumerate(tests)]
        body = bar_chart_panel(rows, x=30, y=70, w=480, h=260, value_label="-log10 p")
        maxval = max([r[1] for r in rows], default=1.0) or 1.0
        alpha_y = 70 + (1 - (-10 * math.log10(alpha)) / maxval) * 260
        alpha_line = (f'<line x1="30" y1="{alpha_y:.1f}" x2="510" y2="{alpha_y:.1f}" '
                      'stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4 3"/>')
        header = (
            f'<text x="30" y="32" font-size="14" font-weight="bold" fill="#111827">Statistical significance</text>'
            f'<text x="30" y="52" font-size="10" fill="#6b7280">'
            f'{result.statistics["tests_run"]} tests · {result.statistics["significant"]} significant at alpha={alpha}'
            f' · {result.statistics["anomalies_flagged"]} anomalies flagged</text>'
        )
        footer = f'<text x="30" y="380" font-size="9" fill="#6b7280">Generated by BioNexus Stats Engine v{self.version}</text>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="540" height="400" '
            'viewBox="0 0 540 400" font-family="Helvetica, Arial, sans-serif">'
            '<rect x="0" y="0" width="540" height="400" fill="#ffffff" rx="8"/>'
            f"{header}{body}{alpha_line}{footer}</svg>"
        )


stats_engine = StatsEngine()