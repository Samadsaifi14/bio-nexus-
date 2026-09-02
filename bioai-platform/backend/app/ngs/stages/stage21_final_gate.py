"""
Stage 21 — Final analysis-readiness gate (blueprint Stage 21). The last word.

This is NOT another QC tool — it is the platform's aggregate decision over everything the
pipeline has seen. It walks the accumulated per-stage results and decides whether the data are
fit for *clinical interpretation*:

    ANALYSIS_READY               every stage PASSed; nothing blocks
    ANALYSIS_READY_WITH_WARNINGS at least one mild stage WARNed (proceed, but surface it)
    NOT_ANALYSIS_READY           a fail-blocking gate (input integrity / reference /
                                 contamination / identity) failed -> the run must not be
                                 interpreted

Crucially the gate is *evidence-preserving*: the reason for every non-READY verdict lists the
specific blocking stage(s) and their observed metrics, so a lab can see exactly why a result
was withheld. Fail-blocking stages are distinguished from mild stages (which only warn).
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule, Decision

# stage -> whether a FAIL there is hard blocking (must not be interpreted)
BLOCKING = {
    "input_validation": True,
    "reference_validation": True,
    "contamination": True,
    "identity": True,
    # all other stages are "mild": a failed metric there only warns / continues
}


def evaluate_gate(pipeline_report: dict) -> dict:
    """Read a pipeline report (orchestrator.Pipeline.report) and produce the readiness verdict."""
    stages = pipeline_report.get("stages", [])
    blocked = []
    warners = []
    passed = 0
    for s in stages:
        step = s.get("step")
        decision = s.get("decision")
        qc = s.get("qc") or {}
        status = qc.get("status")
        if decision == "STOP" or (status == "FAIL" and BLOCKING.get(step)):
            blocked.append({
                "stage": step,
                "tool": s.get("tool"),
                "status": "FAIL",
                "metrics": {m["name"]: m["value"] for m in qc.get("metrics", [])},
            })
        elif status == "WARN":
            warners.append({
                "stage": step,
                "metrics": {m["name"]: m["value"] for m in qc.get("metrics", [])},
            })
        else:
            passed += 1

    if blocked:
        verdict = "NOT_ANALYSIS_READY"
    elif warners:
        verdict = "ANALYSIS_READY_WITH_WARNINGS"
    else:
        verdict = "ANALYSIS_READY"

    return {
        "verdict": verdict,
        "blocking_stages": blocked,
        "warning_stages": warners,
        "stages_passed": passed,
        "stages_total": len(stages),
        "summary": (
            f"{verdict}: {len(blocked)} blocking gate(s) failed"
            if blocked else
            (f"{verdict}: proceeding with {len(warners)} warning(s)"
             if warners else f"all {passed} pipeline stages passed")),
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
        version="0.1.0",
        inputs=["pipeline_report"],
        outputs=["readiness_verdict"],
        rules=[
            ThresholdRule(
                name="readiness_verdict", metric="readiness_verdict",
                evaluate=lambda v: _gate_rule(v),
                expectation="ANALYSIS_READY or ANALYSIS_READY_WITH_WARNINGS",
            ),
        ],
        fail_blocks=True,   # a NOT_READY verdict stops the report from being finalised
        run=_stage21_run,
    )


def _gate_rule(v):
    if v == "ANALYSIS_READY":
        return QcStatus.PASS
    if v == "ANALYSIS_READY_WITH_WARNINGS":
        return QcStatus.WARN
    return QcStatus.FAIL


def run_final_gate(pipeline_report: dict) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    gate = evaluate_gate(pipeline_report)
    contract = stage21_contract()
    result = QcResult.from_metrics(apply_rules(
        contract.resolve_rules({}), {"readiness_verdict": gate["verdict"]}),
                                   fail_blocks=True)
    return {
        "result": {"step": "final_gate", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": gate},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "verdict": gate["verdict"], "blocking_stages": gate["blocking_stages"],
                    "warning_stages": gate["warning_stages"]},
    }
