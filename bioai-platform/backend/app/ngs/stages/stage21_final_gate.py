"""
Stage 21 — final analysis-readiness gate.

The gate separates measured warnings/failures from explicit ``NOT_EVALUATED``
evidence. Missing optional evidence is never represented as zero, PASS, FAIL, or
a biological negative finding. The software readiness gate nevertheless remains
conservative: a run with missing checks is ``ANALYSIS_READY_WITH_WARNINGS`` until
those checks are supplied.

The user-facing NGS summary can therefore present measured QC independently while
Methods/provenance retains the conservative software gate.
"""
from __future__ import annotations

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule

BLOCKING = {
    "input_validation": True,
    "reference_validation": True,
    "contamination": True,
    "identity": True,
}


def _is_not_evaluated(stage: dict) -> bool:
    data = stage.get("data") or {}
    return data.get("status") == "NOT_EVALUATED" or bool(data.get("unevaluated"))


def evaluate_gate(pipeline_report: dict) -> dict:
    stages = pipeline_report.get("stages", [])
    blocked: list[dict] = []
    warners: list[dict] = []
    not_evaluated: list[dict] = []
    passed = 0

    for stage in stages:
        step = stage.get("step")
        qc = stage.get("qc") or {}
        decision = stage.get("decision")
        status = qc.get("status")

        if _is_not_evaluated(stage):
            data = stage.get("data") or {}
            not_evaluated.append({
                "stage": step,
                "tool": stage.get("tool"),
                "reason": data.get("unevaluated") or data.get("reason") or "No measurement was produced by this preview.",
            })
            continue

        metrics = {metric.get("name"): metric.get("value") for metric in qc.get("metrics", [])}
        if decision == "STOP" or (status == "FAIL" and BLOCKING.get(step)):
            blocked.append({
                "stage": step,
                "tool": stage.get("tool"),
                "status": "FAIL",
                "metrics": metrics,
            })
        elif status in {"WARN", "FAIL"}:
            warners.append({"stage": step, "status": status, "metrics": metrics})
        else:
            passed += 1

    if blocked:
        verdict = "NOT_ANALYSIS_READY"
    elif warners or not_evaluated:
        verdict = "ANALYSIS_READY_WITH_WARNINGS"
    else:
        verdict = "ANALYSIS_READY"

    evaluated_total = len(stages) - len(not_evaluated)
    if blocked:
        summary = f"{verdict}: {len(blocked)} blocking evaluated stage(s) failed"
    elif warners:
        summary = f"{verdict}: {len(warners)} evaluated stage(s) require review; {len(not_evaluated)} stage(s) not evaluated"
    elif not_evaluated:
        summary = f"{verdict}: measured stages passed; {len(not_evaluated)} stage(s) remain not evaluated"
    else:
        summary = f"{verdict}: all {evaluated_total} evaluated stage(s) passed"

    return {
        "verdict": verdict,
        "blocking_stages": blocked,
        "warning_stages": warners,
        "not_evaluated_stages": not_evaluated,
        "stages_passed": passed,
        "stages_evaluated": evaluated_total,
        "stages_total": len(stages),
        "summary": summary,
        "interpretation": (
            "NOT_EVALUATED means no measurement was produced. It is kept separate "
            "from measured WARN/FAIL evidence and is not a negative biological finding."
        ),
    }


def _stage21_run(sample: dict, state: dict) -> tuple[dict, dict]:
    report = sample.get("pipeline_report") or state.get("pipeline_report")
    if report is None:
        return {"error": "final gate needs the pipeline report"}, {"readiness_verdict": "NOT_ANALYSIS_READY"}
    gate = evaluate_gate(report)
    state.setdefault("final_gate", {})["result"] = gate
    return gate, {"readiness_verdict": gate["verdict"]}


def stage21_contract() -> StageContract:
    return StageContract(
        step="final_gate",
        tool="platform-analysis-readiness",
        version="0.2.0",
        inputs=["pipeline_report"],
        outputs=["readiness_verdict"],
        rules=[
            ThresholdRule(
                name="readiness_verdict",
                metric="readiness_verdict",
                evaluate=_gate_rule,
                expectation="ANALYSIS_READY or ANALYSIS_READY_WITH_WARNINGS",
            ),
        ],
        fail_blocks=True,
        run=_stage21_run,
    )


def _gate_rule(value):
    if value == "ANALYSIS_READY":
        return QcStatus.PASS
    if value == "ANALYSIS_READY_WITH_WARNINGS":
        return QcStatus.WARN
    return QcStatus.FAIL


def run_final_gate(pipeline_report: dict) -> dict:
    from app.ngs.contracts import QcResult, apply_rules

    gate = evaluate_gate(pipeline_report)
    contract = stage21_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"readiness_verdict": gate["verdict"]}),
        fail_blocks=True,
    )
    return {
        "result": {
            "step": "final_gate",
            "qc": result.to_dict(),
            "decision": result.decision.value,
            "data": gate,
        },
        "summary": {
            "status": result.status.value,
            "decision": result.decision.value,
            "verdict": gate["verdict"],
            "blocking_stages": gate["blocking_stages"],
            "warning_stages": gate["warning_stages"],
            "not_evaluated_stages": gate["not_evaluated_stages"],
        },
    }
