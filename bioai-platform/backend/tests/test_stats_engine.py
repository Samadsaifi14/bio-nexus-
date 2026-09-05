"""Statistical Engine (Component 19) unit tests — dependency-free."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, stats_engine
from app.engines.stats_engine import mann_whitney_u, welch_t, z_score_anomalies

GROUP_A = [5.1, 5.4, 5.2, 5.0, 5.3, 5.1, 5.2, 5.0, 5.4, 5.3]
GROUP_B = [8.2, 8.4, 7.9, 8.1, 8.3, 8.0, 8.2, 8.4, 7.8, 8.1]
IDENTICAL_A = [2.0, 2.0, 2.0, 2.0, 2.0]


def test_registered_in_registry():
    assert "stats" in ENGINES


def test_welch_detects_separated_groups():
    r = welch_t(GROUP_A, GROUP_B)
    assert r["statistic"] < 0
    assert r["p_value"] < 0.001
    assert r["significant"] is True
    assert abs(r["mean_a"] - 5.2) < 0.01
    assert abs(r["mean_b"] - 8.14) < 0.01
    assert r["effect_size"] < -3.0


def test_welch_identical_groups_not_significant():
    r = welch_t(GROUP_B, GROUP_B)
    assert r["p_value"] >= 0.9
    assert r["significant"] is False


def test_welch_insufficient_samples_flags():
    r = welch_t([1.0], [2.0, 3.0, 4.0])
    assert math.isnan(r["statistic"])
    assert r["significant"] is False


def test_mann_whitney_rank_difference():
    r = mann_whitney_u(GROUP_A, GROUP_B)
    assert r["p_value"] < 0.01
    assert r["significant"] is True
    assert 0 <= r["statistic"] <= len(GROUP_A) * len(GROUP_B)


def test_z_score_anomalies_flags_outlier():
    values = [1.0, 1.01, 0.99, 1.02, 1.0, 1.01, 0.98, 9.5]
    out = z_score_anomalies(values, threshold=2.0)
    flagged = [a for a in out if a["flagged"]]
    assert len(flagged) == 1
    assert flagged[0]["value"] == 9.5


def test_parse_run_and_validate_ok():
    result = stats_engine.parse({
        "alpha": 0.05,
        "tests": [
            {"name": "tp53_vs_gfp", "type": "welch_t", "group_a": GROUP_A, "group_b": GROUP_B},
            {"name": "rank_delta", "type": "mann_whitney_u", "group_a": GROUP_A, "group_b": GROUP_B},
        ],
        "values": [1.0, 1.0, 1.0, 9.5],
    })
    assert result.statistics["tests_run"] == 2
    assert result.statistics["significant"] == 2
    report = stats_engine.validate(result)
    assert report.valid, [c for c in report.checks if not c["passed"]]


def test_validate_fails_tiny_samples():
    result = stats_engine.parse({
        "tests": [{"name": "small", "type": "welch_t", "group_a": [1, 2], "group_b": [3, 4]}],
    })
    report = stats_engine.validate(result)
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "sample_sizes_sufficient" in names
    assert not report.valid


def test_validate_fails_bad_alpha():
    result = stats_engine.parse({"alpha": 1.5, "tests": [
        {"name": "t", "type": "welch_t", "group_a": GROUP_A, "group_b": GROUP_B}]})
    report = stats_engine.validate(result)
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "alpha_bounded" in names


def test_export_csv_and_figure():
    result = stats_engine.parse({"tests": [
        {"name": "a", "type": "welch_t", "group_a": GROUP_A, "group_b": GROUP_B}]})
    csv = stats_engine.export(result, "csv")
    assert csv.startswith("test,method,statistic,p_value,significant,effect_size,n_a,n_b")
    assert len(csv.splitlines()) == 2
    svg = stats_engine.figure(result)
    assert "Statistical significance" in svg
    assert svg.count("<svg") == svg.count("</svg>")


def test_validate_empty_degrades():
    assert not stats_engine.validate(stats_engine.parse(None)).valid