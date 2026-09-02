"""
Stage 14 — Filtering engine (blueprint Stage 14).

After QC, variants are filtered relationally in a *single transparent pass* against rules the
platform makes visible (the evidence chain). For a germline rare-disease / hereditary-cancer
panel the defaults are:

    * keep only biallelic
    * keep only variants that survived QC (status != FAIL)   [variant QC]
    * drop common variants: gnomAD AF >= 0.01 (a ~1% MAF threshold) -> REJECT (COMMON)
    * keep the rest as final candidates

Every decision records *which* rule fired so the user sees the chain, not a magic result.
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import StageContract, ThresholdRule


def _is_common(v: dict, max_af: float) -> bool:
    af = v.get("gnomad_af")
    if af is None:
        return False
    try:
        return float(af) >= max_af
    except (TypeError, ValueError):
        return False


def filter_variants(variants: list[dict], max_af: float = 0.01) -> dict:
    final = []
    rejected = []
    for v in variants:
        reasons: list[str] = []

        if v.get("variant_type") == "somatic":
            # somatic classifier flags, not frequency-filtered the same way
            pass
        else:
            if not v.get("biallelic", True):
                reasons.append("multiallelic")
            if v.get("qc", {}).get("status") == "FAIL":
                reasons.append("fail_variant_qc")
            if _is_common(v, max_af):
                reasons.append(f"common_population_af>={max_af}")

        if reasons:
            rv = dict(v)
            rv["filter"] = "REJECT"
            rv["filter_reasons"] = reasons
            rejected.append(rv)
        else:
            fv = dict(v)
            fv["filter"] = "PASS"
            fv["filter_reasons"] = []
            final.append(fv)

    return {"final": final, "rejected": rejected,
            "n_final": len(final), "n_rejected": len(rejected)}


def _stage14_run(sample: dict, state: dict) -> tuple[dict, dict]:
    variants = state.get("variants", {}).get("qc", {}).get("variants")
    if variants is None:
        variants = state.get("variants", {}).get("normalized")
    if variants is None:
        return {"error": "filtering needs QC'd variants"}, {"filter_completed": 0.0}
    filtered = filter_variants(variants)
    state.setdefault("variants", {})["filtered"] = filtered
    return filtered, {"filter_completed": 100.0}


def stage14_contract() -> StageContract:
    return StageContract(
        step="variant_filter",
        tool="platform-filter-engine",
        version="0.1.0",
        inputs=["qc_variants"],
        outputs=["final_variants"],
        rules=[
            ThresholdRule(name="filter_completed", metric="filter_completed",
                          evaluate=lambda v: _completed_rule(v), expectation="completed"),
        ],
        fail_blocks=False,
        run=_stage14_run,
    )


def _completed_rule(v):
    from app.ngs.contracts import QcStatus
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    return QcStatus.PASS if v >= 100.0 else QcStatus.FAIL


def run_variant_filter(variants: list[dict], max_af: float = 0.01) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    filtered = filter_variants(variants, max_af=max_af)
    contract = stage14_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"filter_completed": 100.0}), fail_blocks=False)
    return {
        "result": {"step": "variant_filter", "qc": result.to_dict(),
                   "decision": result.decision.value,
                   "data": {"n_final": filtered["n_final"], "n_rejected": filtered["n_rejected"]}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "final": filtered["final"], "rejected": filtered["rejected"]},
        "variants": filtered,
    }
