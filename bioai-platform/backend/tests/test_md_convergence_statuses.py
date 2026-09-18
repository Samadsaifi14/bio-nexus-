"""MATRIX 15 — MD sampling/convergence status semantics tests.

Deterministic (no OpenMM): exercises MdEngine.convergence against a minimal
stand-in instance with synthetic trajectory series, asserting the machine-
auditable status literals claimed by the verification matrix:
simulation_completed / analysis_completed / sampling_assessment /
convergence_supported_under_metric / convergence_not_established.
"""

from __future__ import annotations

import pytest

from app.md.engine import MdEngine, md_convergence_status


class FakeEngine:
    """Minimal stand-in exposing only what MdEngine.convergence touches."""

    def _cv(self, values):
        import numpy as np
        arr = np.asarray(values, dtype=float)
        mean = float(arr.mean())
        if abs(mean) < 1e-9:
            return None
        return float(arr.std() / abs(mean))

    def __init__(self, drift: float = 0.0):
        # stable series plus a tiny deterministic drift scaled by the metric
        self._drift = drift
        n = 50
        self.rg_series = [{"rg_angstrom": 12.0 + drift * i} for i in range(n)]
        self.production_energy = [-250.0 + drift * i for i in range(n)]
        self.temperature_series = [{"temperature_k": 300.0 + 2 * drift * i} for i in range(n)]

    def _traj_rmsd(self):
        return [{"rmsd": 1.5 + self._drift * i} for i in range(10)]


DRIFT_STABLE = 0.0001    # tiny CV -> all four metrics PASS
DRIFT_UNSTABLE = 3.0     # large CV -> all four metrics WARN


def test_md_convergence_status_literals_documented():
    # the exact literal set claimed by the matrix must be produced
    stable = {"overall": "PASS", "table": [], "status": None}
    table = [
        {"metric": "energy", "status": "PASS", "cv": 0.01},
        {"metric": "temperature", "status": "PASS", "cv": 0.01},
        {"metric": "rmsd", "status": "PASS", "cv": 0.1},
        {"metric": "rg", "status": "PASS", "cv": 0.01},
    ]
    status = md_convergence_status("PASS", table)
    assert status["simulation"] == "simulation_completed"
    assert status["analysis"] == "analysis_completed"
    assert status["sampling_assessment"] == "cv_stability_of_energy_temperature_rmsd_rg"
    assert status["convergence"] == "convergence_supported_under_metric"
    assert status["supported_under_metric"] == ["energy", "rg", "rmsd", "temperature"]


def test_md_convergence_supported_under_metric_when_stable():
    data, metrics = MdEngine.convergence(FakeEngine(DRIFT_STABLE))
    status = data["status"]
    # overall stays WARN because the independent_replica row is always a warn
    # (advanced workflow not auto-run) — but the four real metrics support it
    assert data["overall"] == "WARN"
    assert data["readiness"] == "ANALYSIS_READY_WITH_WARNINGS"
    assert status["simulation"] == "simulation_completed"
    assert status["analysis"] == "analysis_completed"
    assert status["convergence"] == "convergence_supported_under_metric"
    assert status["supported_under_metric"] == ["energy", "rg", "rmsd", "temperature"]
    # metrics must stay consistent with the table
    assert sum(metrics.values()) == len(status["supported_under_metric"])


def test_md_convergence_not_established_when_unstable():
    data, metrics = MdEngine.convergence(FakeEngine(DRIFT_UNSTABLE))
    status = data["status"]
    assert data["overall"] == "WARN"
    assert data["readiness"] == "ANALYSIS_READY_WITH_WARNINGS"
    assert status["convergence"] == "convergence_not_established"
    assert status["supported_under_metric"] == []
    assert sum(metrics.values()) == 0


def test_convergence_never_implied_by_completion():
    # a trajectory that finished but shows no metric support must be labelled
    # convergence_not_established — completion is never conflated with convergence
    table = [
        {"metric": m, "status": "WARN", "cv": 0.9}
        for m in ("energy", "temperature", "rmsd", "rg")
    ] + [{"metric": "independent_replica", "status": "WARN", "cv": None}]
    status = md_convergence_status("WARN", table)
    assert status["simulation"] == "simulation_completed"
    assert status["analysis"] == "analysis_completed"
    assert status["convergence"] == "convergence_not_established"
    assert status["supported_under_metric"] == []


def test_mixed_metrics_report_only_supporting_ones():
    table = [
        {"metric": "energy", "status": "PASS", "cv": 0.03},
        {"metric": "temperature", "status": "PASS", "cv": 0.04},
        {"metric": "rmsd", "status": "WARN", "cv": 0.5},
        {"metric": "rg", "status": "WARN", "cv": 0.4},
    ]
    status = md_convergence_status("WARN", table)
    assert status["convergence"] == "convergence_supported_under_metric"
    assert status["supported_under_metric"] == ["energy", "temperature"]