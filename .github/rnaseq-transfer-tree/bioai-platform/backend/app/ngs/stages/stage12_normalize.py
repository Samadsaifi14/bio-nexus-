"""Minimal VCF allele trimming for the exploratory preview.

Preserve an anchoring base and advance POS when removing a shared prefix.
All ALT alleles remain in their original order, preserving GT/AD/PL indexing.
This is not reference-based left alignment: production indel comparison must
use a reference-aware normalizer such as bcftools norm.
"""

from __future__ import annotations

from app.ngs.contracts import StageContract


def _minimal_alleles(alleles: list[str]) -> tuple[list[str], int]:
    while all(len(a) > 1 for a in alleles) and len({a[-1] for a in alleles}) == 1:
        alleles = [a[:-1] for a in alleles]
    offset = 0
    while all(len(a) > 1 for a in alleles) and len({a[0] for a in alleles}) == 1:
        alleles = [a[1:] for a in alleles]
        offset += 1
    return alleles, offset


def normalize_variants(variants: list[dict]) -> list[dict]:
    out = []
    for v in variants:
        nv = dict(v)
        ref, alt = str(v.get("ref") or "").upper(), str(v.get("alt") or "")
        alts = alt.split(",")
        nv["biallelic"] = len(alts) == 1
        nv["normalization"] = {"method": "minimal_allele_trimming", "reference_left_aligned": False}
        pos = v.get("pos")
        if not isinstance(pos, int) or isinstance(pos, bool) or pos < 1:
            nv["normalization_issue"] = "invalid_or_missing_position"
        elif not ref or not all(alts):
            nv["normalization_issue"] = "empty_allele"
        elif any(set(a.upper()) - set("ACGTN") for a in [ref, *alts]):
            # Symbolic alleles, spanning deletions and breakends need their own
            # semantics. Preserve them verbatim rather than changing their IDs.
            nv["normalization_issue"] = "unsupported_symbolic_or_non_sequence_allele"
        elif ref in [a.upper() for a in alts] or len(set(a.upper() for a in alts)) != len(alts):
            nv["normalization_issue"] = "identical_or_duplicate_allele"
        else:
            alleles, offset = _minimal_alleles([ref, *[a.upper() for a in alts]])
            nv.update(ref=alleles[0], alt=",".join(alleles[1:]), pos=pos + offset)
            if any(len(a) != len(alleles[0]) for a in alleles[1:]):
                nv["normalization"]["requires_reference_left_alignment"] = True
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
        version="0.2.0",
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
