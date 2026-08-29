"""
Stage 18 — Knowledge-DB registry (blueprint Stage 18).

The strongest signal a platform can offer is *which external knowledge* supports a call. This
stage cross-references every annotated variant against **explicitly supplied** knowledge tables
(so nothing is fabricated; the tables come from the deployer):

    clinvar : { (chrom,pos,ref,alt): {"significance": "Pathogenic", "condition": "Hereditary
               breast and ovarian cancer syndrome", "review_status": "criteria_provided"} }
    omim    : { "GENE": {"condition": "...", "mode": "AD", "mim": 113705} }
    gnomad  : { (chrom,pos,ref,alt): {"af": 0.0046, "filters": "PASS", "hom": false} }

For each variant the engine returns the matched ClinVar significance (with discrete tag),
the OMIM condition + inheritance mode for its gene, and the gnomAD frequency + filters. The
aggregate registry view shows how many variants map to pathogenic / VUS / benign categories.
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule

SIG_RANK = {
    "pathogenic": 5, "likely_pathogenic": 4, "vus": 3,
    "likely_benign": 2, "benign": 1, "uncertain": 0,
}


def _key(var: dict) -> tuple:
    return (var.get("chrom"), var.get("pos"), (var.get("ref") or "").upper(),
            (var.get("alt") or "").upper())


def apply_knowledge(variants: list[dict], clinvar=None, omim=None, gnomad=None) -> dict:
    clinvar = clinvar or {}
    omim = omim or {}
    gnomad = gnomad or {}

    out = []
    n_pathogenic = n_vus = n_benign = 0
    for v in variants:
        kv = dict(v)
        key = _key(v)
        gene = (v.get("annotation") or {}).get("gene")

        cv = clinvar.get(key)
        if cv:
            sig = (cv.get("significance") or "").lower().replace(" ", "_")
            kv["clinvar"] = {"significance": cv.get("significance"), "tag": sig,
                             "condition": cv.get("condition"),
                             "review_status": cv.get("review_status")}
            if sig.startswith("pathogenic"):
                n_pathogenic += 1
            elif "benign" in sig:
                n_benign += 1
            elif sig == "vus" or sig == "uncertain":
                n_vus += 1

        om = omim.get(gene)
        if om:
            kv["omim"] = {"gene": gene, "condition": om.get("condition"),
                          "mode": om.get("mode"), "mim": om.get("mim")}

        go = gnomad.get(key)
        if go:
            kv["gnomad"] = {"af": go.get("af"), "filters": go.get("filters"),
                            "homozygotes": go.get("hom", False)}

        out.append(kv)

    return {
        "variants": out,
        "n_pathogenic": n_pathogenic,
        "n_vus": n_vus,
        "n_benign": n_benign,
        "n_total": len(out),
    }


def _stage18_run(sample: dict, state: dict) -> tuple[dict, dict]:
    variants = state.get("variants", {}).get("annotated", {}).get("variants")
    if variants is None:
        return {"error": "knowledge registry needs annotated variants"}, {"kb_ok": 100.0}
    report = apply_knowledge(variants,
                             clinvar=sample.get("clinvar"),
                             omim=sample.get("omim"),
                             gnomad=sample.get("gnomad"))
    state.setdefault("variants", {})["knowledge"] = report
    frac = report["n_total"] and (report["n_pathogenic"] + report["n_vus"] +
                                  report["n_benign"]) / report["n_total"] * 100.0
    return report, {"kb_ok": round(frac or 0.0, 3)}


def stage18_contract() -> StageContract:
    return StageContract(
        step="knowledge",
        tool="platform-knowledge-registry",
        version="0.1.0",
        inputs=["annotated_variants", "clinvar", "omim", "gnomad"],
        outputs=["knowledge_variants"],
        rules=[],
        fail_blocks=False,
        run=_stage18_run,
    )


def run_knowledge_stage(variants: list[dict], clinvar=None, omim=None, gnomad=None) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    report = apply_knowledge(variants, clinvar=clinvar, omim=omim, gnomad=gnomad)
    contract = stage18_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), {}), fail_blocks=False)
    return {
        "result": {"step": "knowledge", "qc": result.to_dict(),
                   "decision": result.decision.value,
                   "data": {"n_pathogenic": report["n_pathogenic"],
                            "n_vus": report["n_vus"], "n_benign": report["n_benign"]}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "report": report["variants"]},
        "variants": report["variants"],
    }
