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
    variants = state.get("variants", {}).get("qc", {}).get("variants") or \
        state.get("variants", {}).get("normalized")
    if variants is None:
        return {"error": "filtering needs QC'd variants"}, {"candidate_frac": 0.0}
    filtered = filter_variants(variants)
    state.setdefault("variants", {})["filtered"] = filtered
    total = filtered["n_final"] + filtered["n_rejected"]
    frac = filtered["n_final"] / total * 100.0 if total else 0.0
    return filtered, {"candidate_frac": frac}


def stage14_contract() -> StageContract:
    return StageContract(
        step="variant_filter",
        tool="platform-filter-engine",
        version="0.1.0",
        inputs=["qc_variants"],
        outputs=["final_variants"],
        rules=[
            ThresholdRule(name="candidate_frac", metric="candidate_frac",
                          evaluate=lambda v: _range_rule(v, 0.1, 30.0)),
        ],
        fail_blocks=False,
        run=_stage14_run,
    )


def _range_rule(v, lo, hi):
    from app.ngs.contracts import QcStatus
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    return QcStatus.PASS if lo <= v <= hi else QcStatus.WARN


def run_variant_filter(variants: list[dict], max_af: float = 0.01) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    filtered = filter_variants(variants, max_af=max_af)
    total = filtered["n_final"] + filtered["n_rejected"]
    frac = filtered["n_final"] / total * 100.0 if total else 0.0
    contract = stage14_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"candidate_frac": frac}), fail_blocks=False)
    return {
        "result": {"step": "variant_filter", "qc": result.to_dict(),
                   "decision": result.decision.value,
                   "data": {"n_final": filtered["n_final"], "n_rejected": filtered["n_rejected"]}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "final": filtered["final"], "rejected": filtered["rejected"]},
        "variants": filtered,
    }
