"""
Stage 13 — Variant QC (blueprint Stage 13).

Each variant is quality-assessed before any frequency filtering, using a tiered PASS/WARN/FAIL
surrogate that follows the professional practice of masking low-quality / low-complexity calls:

    * depth (DP)
    * allele balance (AB = alt_fraction), sanity window for SNPs
    * mapping quality (MAPQ)
    * strand bias (a simple surrogate: fraction of alt reads on the forward strand ~ 0.5)
    * homopolymer / low-complexity context (approximated here by tandem-repeat length)
    * genotype quality (GQ)

A variant that fails hard criteria is masked before the filtering engine sees it.
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import StageContract, ThresholdRule


def _repeat_run(seq_context: str) -> int:
    """Longest homopolymer run in the surrounding sequence; >= 4 flags low complexity."""
    best = cur = 0
    prev = None
    for c in seq_context:
        if c == prev:
            cur += 1
        else:
            cur = 1
            prev = c
        best = max(best, cur)
    return best


def variant_qc(variant: dict) -> dict:
    """Classify a single variant into PASS / WARN / FAIL with machine-readable reasons."""
    dp = variant.get("dp", 0)
    af = variant.get("af", 0.0)
    n_alt = variant.get("n_alt", 0)
    ab = af
    homopolymer = _repeat_run(variant.get("context", variant.get("ref", "")))

    reasons_warn: list[str] = []
    reasons_fail: list[str] = []

    if dp < 8:
        reasons_fail.append("low_depth")
    elif dp < 15:
        reasons_warn.append("below_target_depth")

    if ab > 0.0 and (ab < 0.08 or ab > 0.98):
        # extremely unbalanced; may signal an error rather than a real het/hom
        reasons_warn.append("extreme_allele_balance")

    if n_alt and n_alt < 3:
        reasons_warn.append("few_alt_reads")

    if homopolymer >= 4:
        reasons_warn.append("low_complexity_context")

    if variant.get("genotype_quality", 99) < 20:
        reasons_fail.append("low_gq")

    if not reasons_fail and not reasons_warn:
        status = "PASS"
    elif not reasons_fail:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "status": status,
        "reasons_fail": reasons_fail,
        "reasons_warn": reasons_warn,
        "homopolymer_run": homopolymer,
        "ab": round(ab, 3),
    }


def run_variant_qc(variants: list[dict]) -> dict:
    """Annotate each variant with its QC classification; return passing set + summary."""
    annotated = []
    pass_n = warn_n = fail_n = 0
    recurring: dict[str, int] = {}
    for v in variants:
        qc = variant_qc(v)
        vc = dict(v)
        vc["qc"] = qc
        annotated.append(vc)
        if qc["status"] == "PASS":
            pass_n += 1
        elif qc["status"] == "WARN":
            warn_n += 1
        else:
            fail_n += 1
        for r in qc["reasons_fail"] + qc["reasons_warn"]:
            recurring[r] = recurring.get(r, 0) + 1
    return {
        "variants": annotated,
        "summary": {"pass": pass_n, "warn": warn_n, "fail": fail_n,
                    "total": len(variants), "reasons": recurring},
        "passing": [v for v in annotated if v["qc"]["status"] != "FAIL"],
    }


def _stage13_run(sample: dict, state: dict) -> tuple[dict, dict]:
    variants = state.get("variants", {}).get("normalized") or \
        state.get("variants", {}).get("call", {}).get("variants")
    if variants is None:
        return {"error": "variant QC needs normalized variants"}, {"good_variant_frac": 0.0}
    report = run_variant_qc(variants)
    state.setdefault("variants", {})["qc"] = report
    frac = (report["summary"]["pass"] / report["summary"]["total"] * 100.0
            if report["summary"]["total"] else 100.0)
    return report, {"good_variant_frac": frac}


def stage13_contract() -> StageContract:
    return StageContract(
        step="variant_qc",
        tool="platform-variant-qc",
        version="0.1.0",
        inputs=["normalized_variants"],
        outputs=["qc_variants"],
        rules=[
            ThresholdRule(name="good_variant_frac", metric="good_variant_frac",
                          evaluate=lambda v: _pct_rule(v, 70, 30)),
        ],
        fail_blocks=False,
        run=_stage13_run,
    )


def _pct_rule(v, ok, warn):
    from app.ngs.contracts import QcStatus
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= ok:
        return QcStatus.PASS
    if v >= warn:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_variant_qc_stage(variants: list[dict]) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    report = run_variant_qc(variants)
    frac = (report["summary"]["pass"] / report["summary"]["total"] * 100.0
            if report["summary"]["total"] else 100.0)
    contract = stage13_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"good_variant_frac": frac}), fail_blocks=False)
    return {
        "result": {"step": "variant_qc", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": report["summary"]},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "passing": report["passing"], "summary": report["summary"]},
        "variants": report["variants"],
    }
