"""MD-specific QC rule builders on top of the shared contract engine.

The NGS contract engine (:mod:`app.ngs.contracts`) is assay-agnostic; this module
supplies the MD vocabulary (presence gates, finiteness gates, stability bands) so
the MD pipeline emits machine-auditable PASS / WARN / FAIL metrics with the same
shape as the rest of the platform — "the same platform" for MD and NGS.
"""

from __future__ import annotations

from app.ngs.contracts import QcStatus, ThresholdRule, bounded_rule


def present(metric: str) -> ThresholdRule:
    """A boolean presence gate: value == 1 -> PASS, else FAIL.

    Used for hard requirements (structure parsed, hydrogens added, system
    built, trajectory metrics computed). A failure means the stage could not
    produce a required result and the pipeline must not proceed.
    """

    def _eval(v):
        return QcStatus.PASS if float(v or 0) == 1 else QcStatus.FAIL

    return ThresholdRule(name=metric, metric=metric, evaluate=_eval,
                         expectation="required")


def finite(metric: str) -> ThresholdRule:
    """Finiteness gate: 1 (finite) -> PASS, 0 (NaN / divergence) -> FAIL.

    This is the "if you get NaN, your platform should stop" rule from the MD
    design (module 6).
    """

    def _eval(v):
        return QcStatus.PASS if float(v or 0) == 1 else QcStatus.FAIL

    return ThresholdRule(name=metric, metric=metric, evaluate=_eval,
                         expectation="finite (no NaN)")


def min_value(metric: str, ok_min: float, warn_min: float | None = None,
              unit: str = "") -> ThresholdRule:
    """Minimum-count / higher-better rule (atoms, residues, frames)."""
    return bounded_rule(metric, warn_min=warn_min if warn_min is not None else ok_min,
                        ok_min=ok_min, unit=unit)


def max_value(metric: str, ok_max: float, warn_max: float | None = None,
              unit: str = "") -> ThresholdRule:
    """Maximum / lower-better rule (temperature SD, drift)."""
    rule = bounded_rule(metric, warn_min=warn_max if warn_max is not None else ok_max,
                        ok_min=ok_max, unit=unit, invert=True)
    rule.expectation = f"<= {ok_max}{unit}"
    return rule


def warn_only_present(metric: str) -> ThresholdRule:
    """Presence signal that is never a hard FAIL: 1 -> PASS, else WARN.

    Used for non-blocking informational checks (GROMACS availability, NPT
    not-applicable, convergence rows) so the pipeline can finish with warnings
    instead of spuriously stopping.
    """

    def _eval(v):
        return QcStatus.PASS if float(v or 0) == 1 else QcStatus.WARN

    return ThresholdRule(name=metric, metric=metric, evaluate=_eval,
                         expectation="recommended")
