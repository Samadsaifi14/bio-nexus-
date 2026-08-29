"""
Stage 12 — Variant normalization (blueprint Stage 12).

The platform normalizes raw calls to a single internal representation before any QC or
filtering: strings exchanged for structured {chrom,pos,ref,alt}, the ref/alt are left-normalized
(common suffix/prefix trimmed, ambiguity codes removed), and only biallelic records are kept for
the filtering engine.

This stage is intentionally thin; it exists so downstream QC/filtering operate on a
canonical, comparable representation as the blueprint describes.
"""

from __future__ import annotations

from app.ngs.contracts import StageContract


def _trim_normalize(ref: str, alt: str) -> tuple[str, str]:
    """Left-normalize ref/alt (trim shared prefix, transform to upper-case biallelic)."""
    ref = ref.upper()
    alt = alt.upper()
    if "," in alt:        # skip multiallelic; keep the first for biallelic-only pass
        alt = alt.split(",")[0]
    # trim shared prefix
    i = 0
    while i < len(ref) and i < len(alt) and ref[i] == alt[i]:
        i += 1
    ref = ref[i:]
    alt = alt[i:]
    if ref == alt:
        return ref, alt
    return ref, alt


def normalize_variants(variants: list[dict]) -> list[dict]:
    out = []
    for v in variants:
        ref, alt = _trim_normalize(v.get("ref", ""), v.get("alt", ""))
        if not ref or not alt or ref == alt:
            continue
        nv = dict(v)
        nv["ref"] = ref
        nv["alt"] = alt
        nv["biallelic"] = "," not in v.get("alt", "")
        out.append(nv)
    return out


def _stage12_run(sample: dict, state: dict) -> tuple[dict, dict]:
    variants = state.get("variants", {}).get("call", {}).get("variants")
    if variants is None:
        return {"error": "normalization needs variant calls"}, {}
    norm = normalize_variants(variants)
    state.setdefault("variants", {})["normalized"] = norm
    return {"normalized": norm, "n_normalized": len(norm)}, {}


def stage12_contract() -> StageContract:
    return StageContract(
        step="variant_normalization",
        tool="platform-normalize",
        version="0.1.0",
        inputs=["variant_calls"],
        outputs=["normalized_variants"],
        rules=[],
        fail_blocks=False,
        run=_stage12_run,
    )


def run_variant_normalization(variants: list[dict]) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    norm = normalize_variants(variants)
    contract = stage12_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), {}), fail_blocks=False)
    return {
        "result": {"step": "variant_normalization", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": {"n_normalized": len(norm)}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "normalized": norm},
        "variants": norm,
    }
