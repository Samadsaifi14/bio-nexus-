"""
Stage 11 — Germline variant calling (blueprint Stage 11).

Blueprint reasoning the platform encodes: the primary variant caller (e.g. GATK HaplotypeCaller)
does the heavy lifting; an **orthogonal caller** (e.g. freebayes / bcftools mpileup) runs as a
backup in the same pass so a second opinion exists *without* a second full pipeline. Most
secondary analysis is heuristics downstream of a single high-quality call.

This stage implements both callers as platform surrogates:
    * primary  -> allele-fraction pileup caller (higher sensitivity),
    * orthogonal -> stricter consensus caller (min more reads, higher AF threshold).
The results are merged, discrepancies merely recorded (not fatal), and every variant carries
which caller(s) support it for the evidence chain.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from app.ngs.contracts import StageContract


def _cigar_len(cigar: str) -> int:
    return sum(int(n) for n in re.findall(r"\d+", cigar)) if cigar else 0


def _build_pileup(records: list[dict]) -> dict[str, list[list[str]]]:
    """Per-contig per-position base stacks from mapped, non-dup reads (M-only alignments)."""
    contigs: dict[str, int] = {}
    for r in records:
        if r.get("is_unmapped") or r.get("is_duplicate"):
            continue
        name = r.get("rname", "?")
        end = (r.get("pos", 1) - 1) + _cigar_len(r.get("cigar", ""))
        contigs[name] = max(contigs.get(name, 0), end)
    pile: dict[str, list[list[str]]] = {c: [[] for _ in range(n + 1)] for c, n in contigs.items()}
    for r in records:
        if r.get("is_unmapped") or r.get("is_duplicate"):
            continue
        name = r.get("rname", "?")
        seq = r.get("seq", "")
        start = r.get("pos", 1) - 1        # 0-based index of the first aligned base
        for i, b in enumerate(seq):
            if start + i < len(pile[name]):
                pile[name][start + i].append(b)
    return pile


def _call_primary(pile: dict[str, list[list[str]]], ref: dict[str, str],
                  min_dp: int = 8, min_af: float = 0.2) -> list[dict]:
    variants = []
    for chrom, stacks in pile.items():
        refseq = ref.get(chrom, "")
        for pos, bases in enumerate(stacks):
            if not bases:
                continue
            rb = refseq[pos] if pos < len(refseq) else None
            if not rb or rb not in "ACGT":
                continue
            depth = len(bases)
            counts: dict[str, int] = defaultdict(int)
            for b in bases:
                if b in "ACGTN":
                    counts[b] += 1
            alts = {a: c for a, c in counts.items() if a != rb}
            if not alts:
                continue
            alt, alt_count = max(alts.items(), key=lambda kv: kv[1])
            af = alt_count / depth
            if depth >= min_dp and af >= min_af and alt != "N":
                variants.append({
                    "chrom": chrom, "pos": pos + 1,
                    "ref": rb, "alt": alt, "dp": depth,
                    "af": round(af, 4), "n_alt": alt_count,
                    "type": "SNP",
                })
    return variants


def _call_orthogonal(variants: list[dict], min_dp: int = 12, min_af: float = 0.35) -> list[dict]:
    return [v for v in variants if v["dp"] >= min_dp and v["af"] >= min_af]


def call_variants(
    records: list[dict],
    ref_seq: dict[str, str],
    min_dp: int = 8,
    min_af: float = 0.2,
) -> dict:
    """Run primary + orthogonal calls and merge with per-caller support tags."""
    pile = _build_pileup(records)
    primary = _call_primary(pile, ref_seq, min_dp=min_dp, min_af=min_af)
    orthogonal = _call_orthogonal(primary)
    ortho_keys = {(v["chrom"], v["pos"]) for v in orthogonal}
    for v in primary:
        v["callers"] = ["primary"]
        if (v["chrom"], v["pos"]) in ortho_keys:
            v["callers"].append("orthogonal")
        v["concordant"] = len(v["callers"]) > 1
    # record discrepancies
    discordant = [v for v in primary if not v["concordant"]]
    return {
        "variants": primary,
        "n_primary": len(primary),
        "n_orthogonal": len(orthogonal),
        "discordant": discordant,
        "callers": {"primary": "platform-haplotype", "orthogonal": "platform-freya"},
    }


def _stage11_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    ref_seq = sample.get("reference_seq") or state.get("reference_seq")
    if not records:
        return {"error": "variant calling needs aligned records"}, {}
    ref_map = {sample.get("contig", "chr1"): ref_seq} if isinstance(ref_seq, str) else (ref_seq or {"chr1": ""})
    vcf = call_variants(records, ref_map)
    state.setdefault("variants", {})["call"] = vcf
    return vcf, {"variants_called": len(vcf["variants"])}


def stage11_contract() -> StageContract:
    return StageContract(
        step="variant_calling",
        tool="platform-haplotype + platform-freya (orthogonal)",
        version="0.1.0",
        inputs=["processed_bam", "reference_sequence"],
        outputs=["variant_calls"],
        rules=[],
        fail_blocks=False,
        run=_stage11_run,
        evidence_level="SURROGATE",
    )


def run_variant_calling(
    records: list[dict],
    ref_seq: dict[str, str],
    min_dp: int = 8,
    min_af: float = 0.2,
) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    vcf = call_variants(records, ref_seq, min_dp=min_dp, min_af=min_af)
    contract = stage11_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), {}), fail_blocks=False)
    return {
        "result": {"step": "variant_calling", "qc": result.to_dict(),
                   "decision": result.decision.value,
                   "data": {"n_primary": vcf["n_primary"], "n_orthogonal": vcf["n_orthogonal"],
                            "n_discordant": len(vcf["discordant"])}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "variants": vcf["variants"], "callers": vcf["callers"]},
        "variants": vcf,
    }
