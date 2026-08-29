"""
QC contract engine.

This is the machine-auditable backbone every pipeline stage plugs into (blueprint Stage 31).
Each process declares:

    INPUT CONTRACT    what the stage consumes
    OUTPUT CONTRACT   what the stage produces
    QC CONTRACT       required metrics, each with an assay-aware threshold rule
    DECISION CONTRACT PASS / WARN / FAIL -> how the orchestrator should proceed

A stage result looks like:

    {
      "step": "alignment",
      "tool": "bwa-mem2",
      "version": "2.2.1",
      "input": ["clean_R1", "clean_R2"],
      "output": ["sample.bam"],
      "qc": {
        "mapping_rate": {"value": 97.8, "status": "PASS"},
        "proper_pair":   {"value": 96.2, "status": "PASS"}
      },
      "decision": "CONTINUE"
    }

Thresholds are NOT one universal set of constants. They are wrapped in rules that can depend
on the assay, platform, read length, library type and sample type (inherited per sample), so a
WGS germline sample and a targeted amplicon sample are judged against appropriate expectations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Status / decision
# ---------------------------------------------------------------------------


class QcStatus(str, Enum):
    """The QC state of a metric or a stage."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class Decision(str, Enum):
    """The orchestrator's next action based on a stage's QC."""

    CONTINUE = "CONTINUE"                  # proceed to the next stage
    CONTINUE_WITH_WARNING = "CONTINUE_WITH_WARNING"  # proceed but surface a warning
    STOP = "STOP"                          # block downstream (e.g. contamination FAIL)


# ---------------------------------------------------------------------------
# Metric + threshold rules
# ---------------------------------------------------------------------------


@dataclass
class Metric:
    """A single measured value with a computed status."""

    name: str
    value: Any
    status: QcStatus = QcStatus.PASS
    expected: Optional[str] = None     # human-readable expectation, e.g. ">= 90%"
    detail: Optional[str] = None       # free-form explanation


@dataclass
class ThresholdRule:
    """Defines how to turn a measured value into a PASS / WARN / FAIL status.

    ``evaluate(value) -> QcStatus`` must be provided. A rule is deliberately encoded as a
    callable so it can be built from an assay-aware spec (see below) or hand-rolled for a
    metric that has no clean numeric boundary.
    """

    name: str
    metric: str
    evaluate: Callable[[Any], QcStatus]
    expectation: Optional[str] = None
    optional: bool = False   # missing metric -> WARN (not FAIL); used for conditional sub-checks

    def apply(self, value: Any, detail: Optional[str] = None) -> Metric:
        return Metric(
            name=self.metric,
            value=value,
            status=self.evaluate(value),
            expected=self.expectation,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Reusable rule builders (assay-aware)
# ---------------------------------------------------------------------------


def bounded_rule(
    metric: str,
    *,
    warn_min: float,
    ok_min: float,
    max_value: Optional[float] = None,
    unit: str = "",
    invert: bool = False,
) -> ThresholdRule:
    """Numeric threshold rule with a WARN band.

    Higher-is-better (default): value >= ok_min -> PASS; >= warn_min -> WARN; else FAIL.
    Lower-is-better (``invert=True``, e.g. duplication % / contamination %): value <= ok_min
    -> PASS; <= warn_min -> WARN; else FAIL. ``max_value`` is accepted for call-site clarity
    but only the ok/warn thresholds drive the outcome.
    """
    expectation = f"{'<=' if invert else '>='} {ok_min}{unit}"

    def _eval(value: Any) -> QcStatus:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return QcStatus.FAIL
        if invert:
            if v <= ok_min:
                return QcStatus.PASS
            if v <= warn_min:
                return QcStatus.WARN
            return QcStatus.FAIL
        if v >= ok_min:
            return QcStatus.PASS
        if v >= warn_min:
            return QcStatus.WARN
        return QcStatus.FAIL

    return ThresholdRule(name=metric, metric=metric, evaluate=_eval, expectation=expectation)


def apply_rules(rules: list[ThresholdRule], values: dict[str, Any]) -> list[Metric]:
    """Apply a list of rules against a {metric_name: value} map.

    Missing metrics are reported as FAIL so the orchestrator notices when a stage fails to
    produce a required metric (a broken / failed run surfaces immediately).
    """
    metrics: list[Metric] = []
    for rule in rules:
        if rule.metric in values:
            metrics.append(rule.apply(values[rule.metric]))
        elif rule.optional:
            metrics.append(
                Metric(name=rule.metric, value=None, status=QcStatus.WARN, expected=rule.expectation,
                       detail="optional metric not evaluated (no reference data supplied)")
            )
        else:
            metrics.append(
                Metric(name=rule.metric, value=None, status=QcStatus.FAIL, expected=rule.expectation,
                       detail="metric missing from stage output")
            )
    return metrics


# ---------------------------------------------------------------------------
# Stage-level aggregation
# ---------------------------------------------------------------------------


def _worst(metrics: list[Metric]) -> QcStatus:
    order = {QcStatus.PASS: 0, QcStatus.WARN: 1, QcStatus.FAIL: 2}
    worst = QcStatus.PASS
    for m in metrics:
        if order[m.status] > order[worst]:
            worst = m.status
    return worst


def decision_for(stage_status: QcStatus, *, fail_blocks: bool = True) -> Decision:
    """Map a stage's aggregate status to an orchestrator decision.

    ``fail_blocks=True`` stages (e.g. contamination, identity) must STOP on FAIL; mild stages
    (e.g. duplication) may be configured to only WARN.
    """
    if stage_status == QcStatus.FAIL:
        return Decision.STOP if fail_blocks else Decision.CONTINUE_WITH_WARNING
    if stage_status == QcStatus.WARN:
        return Decision.CONTINUE_WITH_WARNING
    return Decision.CONTINUE


@dataclass
class QcResult:
    """Aggregate QC for one stage or for the whole run."""

    status: QcStatus = QcStatus.PASS
    decision: Decision = Decision.CONTINUE
    metrics: list[Metric] = field(default_factory=list)

    @classmethod
    def from_metrics(cls, metrics: list[Metric], *, fail_blocks: bool = True) -> "QcResult":
        status = _worst(metrics)
        return cls(status=status, decision=decision_for(status, fail_blocks=fail_blocks), metrics=metrics)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "decision": self.decision.value,
            "metrics": [
                {"name": m.name, "value": m.value, "status": m.status.value,
                 "expected": m.expected, "detail": m.detail}
                for m in self.metrics
            ],
        }


@dataclass
class StageResult:
    """The full per-stage machine-auditable record (blueprint Stage 31)."""

    step: str
    tool: str
    version: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    qc: Optional[QcResult] = None
    decision: Decision = Decision.CONTINUE
    data: dict = field(default_factory=dict)   # stage-specific payload (parsed results)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "tool": self.tool,
            "version": self.version,
            "input": self.inputs,
            "output": self.outputs,
            "qc": self.qc.to_dict() if self.qc else None,
            "decision": self.decision.value,
            "data": self.data,
        }


# ---------------------------------------------------------------------------
# Contract runner
# ---------------------------------------------------------------------------


@dataclass
class StageContract:
    """Declarative definition of one stage's contract.

    Encapsulates the blueprint's INPUT / OUTPUT / QC / DECISION contracts plus the execution
    callable. The callable receives the parsed sample context and returns:
        (stage_data: dict, metric_values: dict[str, Any])
    so the engine computes QC + decision uniformly.
    """

    step: str
    tool: str
    version: str
    inputs: list[str]
    outputs: list[str]
    # rules can be a fixed list, or a callable that resolves assay-aware rules from the sample.
    rules: Any
    fail_blocks: bool = True
    run: Optional[Callable[[dict, dict], tuple[dict, dict]]] = None
    expectation: Optional[str] = None

    def resolve_rules(self, sample: dict) -> list[ThresholdRule]:
        if callable(self.rules):
            resolved = self.rules(sample)
            return list(resolved) if resolved is not None else []
        return list(self.rules)

    def evaluate(self, metric_values: dict[str, Any], sample: Optional[dict] = None) -> QcResult:
        rules = self.resolve_rules(sample or {})
        metrics = apply_rules(rules, metric_values)
        return QcResult.from_metrics(metrics, fail_blocks=self.fail_blocks)


def run_contract(contract: StageContract, sample: dict, stage_state: dict) -> StageResult:
    """Execute a stage's callable and wrap its output in a machine-auditable StageResult."""
    data: dict = {}
    metric_values: dict = {}
    if contract.run is not None:
        try:
            data, metric_values = contract.run(sample, stage_state)
        except Exception as exc:  # any failure becomes a FAIL contract
            data = {"error": str(exc)}
            metric_values = {}
    qc = contract.evaluate(metric_values, sample)
    return StageResult(
        step=contract.step,
        tool=contract.tool,
        version=contract.version,
        inputs=contract.inputs,
        outputs=contract.outputs,
        qc=qc,
        decision=qc.decision,
        data=data,
    )


def evaluate_metric(rule: ThresholdRule, value: Any) -> Metric:
    return rule.apply(value)


def evaluate_contract(contract: StageContract, metric_values: dict[str, Any]) -> QcResult:
    return contract.evaluate(metric_values)
