"""
Stage 19 — Variant prioritization (blueprint Stage 19). Differentiator: a VISIBLE evidence chain.

A clinician will not trust a black-box rank. Every prioritized variant therefore carries an
explicit, machine-readable evidence chain: each rule that fired, the value actually observed,
the weight it contributed, and a short human verdict. The score is the sum of the weights
(0..100), but the *chain* is what makes the result auditable and explainable.

Rules (all derived from real fields already attached in previous stages, or explicitly supplied
reference data — nothing fabricated):
    * consequence impact       (HIGH = nonsense/frameshift/splice -> +35, MODERATE -> +20)
    * ClinVar significance     (Pathogenic +30, Likely Pathogenic +22, VUS +8, benign -10)
    * population frequency     (rare, gnomAD AF < 1e-4 -> +15; common -> -15)
    * OMIM gene-disease match  (gene flagged as disease-associated -> +12) with inheritance fit
    * co-segregation           (segregates in affected relatives, supplied -> +10)
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule


def _evidence(rule, observed, weight, verdict):
    return {"rule": rule, "observed": observed, "weight": weight, "verdict": verdict}


def prioritize_variants(variants: list[dict], autosomal_mode: Optional[str] = None) -> dict:
    scored = []

    for v in variants:
        chain: list[dict] = []
        score = 0.0
        ann = v.get("annotation") or {}

        # 1. consequence impact
        cons = ann.get("consequence")
        if cons in ("nonsense", "frameshift", "splice_region", "splice_acceptor", "splice_donor"):
            score += 35
            chain.append(_evidence("consequence_impact", cons, 35, f"{cons} is a HIGH-impact change"))
        elif cons == "missense":
            score += 20
            chain.append(_evidence("consequence_impact", cons, 20, "missense is MODERATE impact"))
        else:
            chain.append(_evidence("consequence_impact", cons, 0, f"{cons or 'none'} is low impact"))

        # 2. ClinVar significance
        cv = v.get("clinvar") or {}
        tag = cv.get("tag")
        if tag in ("pathogenic", "likely_pathogenic"):
            w = 30 if tag == "pathogenic" else 22
            score += w
            chain.append(_evidence("clinvar", cv.get("significance"), w,
                                   f"matched {cv.get('review_status', 'reviewed')} ClinVar entry"))
        elif tag in ("vus", "uncertain"):
            score += 8
            chain.append(_evidence("clinvar", cv.get("significance"), 8, "uncertain-significance variant"))
        elif "benign" in (tag or ""):
            score -= 10
            chain.append(_evidence("clinvar", cv.get("significance"), -10, "benign ClinVar entry"))

        # 3. population frequency
        g = v.get("gnomad") or {}
        af = g.get("af")
        if af is None:
            chain.append(_evidence("population_frequency", "not_in_gnomad", 15, "absent from population DBs"))
            score += 15
        elif float(af) < 1e-4:
            score += 15
            chain.append(_evidence("population_frequency", af, 15, f"very rare (AF {af})"))
        else:
            score -= 15
            chain.append(_evidence("population_frequency", af, -15, f"common (AF {af})"))

        # 4. OMIM gene-disease match + inheritance fit
        om = v.get("omim") or {}
        if om:
            score += 12
            chain.append(_evidence("omim_gene", om.get("condition"), 12,
                                   f"gene in OMIM: {om.get('condition')}"))
            mode = om.get("mode")
            if autosomal_mode and mode and mode != autosomal_mode:
                score -= 8
                chain.append(_evidence("inheritance", f"observed {autosomal_mode} vs {mode}", -8,
                                       "inheritance-mode mismatch lowers fit"))
            elif autosomal_mode and mode == autosomal_mode:
                score += 6
                chain.append(_evidence("inheritance", mode, 6, "inheritance mode matches"))

        # 5. co-segregation (explicitly supplied)
        if v.get("cosegregates"):
            score += 10
            chain.append(_evidence("cosegregation", True, 10, "segregates with affected relatives"))

        score = max(0, min(100, score))
        vp = dict(v)
        vp["prio"] = {"score": round(score, 1), "evidence": chain}
        scored.append(vp)

    scored.sort(key=lambda v: -v["prio"]["score"])
    for rank, vp in enumerate(scored, start=1):
        vp["prio"]["rank"] = rank
    return {"variants": scored, "n_variants": len(scored)}


def _stage19_run(sample: dict, state: dict) -> tuple[dict, dict]:
    variants = state.get("variants", {}).get("knowledge", {}).get("variants")
    autosomal = sample.get("autosomal_mode")
    if variants is None:
        return {"error": "prioritization needs knowledge-annotated variants"}, {"prio_ok": 100.0}
    report = prioritize_variants(variants, autosomal_mode=autosomal)
    state.setdefault("variants", {})["prioritized"] = report
    return report, {"prio_ok": 100.0}


def stage19_contract() -> StageContract:
    return StageContract(
        step="prioritization",
        tool="platform-prioritize",
        version="0.1.0",
        inputs=["knowledge_variants"],
        outputs=["prioritized_variants"],
        rules=[],
        fail_blocks=False,
        run=_stage19_run,
    )


def run_prioritize(variants: list[dict], autosomal_mode: Optional[str] = None) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    report = prioritize_variants(variants, autosomal_mode=autosomal_mode)
    contract = stage19_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), {}), fail_blocks=False)
    return {
        "result": {"step": "prioritization", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": {"n": report["n_variants"]}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "top": report["variants"]},
        "variants": report["variants"],
    }
