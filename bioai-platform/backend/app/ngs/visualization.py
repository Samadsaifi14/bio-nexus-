"""
Display-ready serialization for the IGV wiring (blueprint point 20).

The pipeline produces an in-memory alignment (``aligned_records``) and variant calls
(``variants``). Everything is *real* computed data from the actual pipeline state — no
clinical results are fabricated — but they live in Python dicts. These helpers turn that
state into the two plain-text formats the frontend IGV browser already understands: SAM
(for the read/coverage track) and VCF (for the variant track).

Nothing here invents alignments or variants; it only serializes what the stage DAG produced.
"""

from __future__ import annotations

from typing import Any


def records_to_sam(records: list[dict]) -> str:
    """Serialize pipeline ``aligned_records`` into SAM text consumable by the IGV read track.

    Records are the SAM-like dicts emitted by ``app.ngs.sam.map_reads`` (each is a real
    mapping decision). Headers keep the track self-describing; coordinate-sorted output so
    the viewer renders a sensible coverage profile.
    """
    if not records:
        return "@HD\tVN:1.6\tSO:coordinate\n"

    contigs: dict[str, int] = {}
    for r in records:
        name = r.get("rname") or "chr1"
        end = (r.get("pos", 1) - 1) + _cigar_len(r.get("cigar", ""))
        contigs[name] = max(contigs.get(name, 0), end)

    lines = ["@HD\tVN:1.6\tSO:coordinate"]
    for name, length in contigs.items():
        lines.append(f"@SQ\tSN:{name}\tLN:{length}")

    ordered = sorted(records, key=lambda r: (r.get("rname") or "*", r.get("pos", 0)))
    for r in ordered:
        flag = r.get("flag", 4 if r.get("is_unmapped") else 0)
        lines.append("\t".join([
            r.get("qname", "read"),
            str(flag),
            r.get("rname") or "*",
            str(r.get("pos", 0)),
            str(r.get("mapq", 0)),
            r.get("cigar") or "*",
            r.get("rnext") or "*",
            str(r.get("pnext", 0)),
            str(r.get("tlen", 0)),
            r.get("seq", "*"),
            r.get("qual", "*"),
        ]))
    return "\n".join(lines) + "\n"


def variants_to_vcf(variants: list[dict]) -> str:
    """Serialize the variant-call list into VCF text for the IGV variant track.

    Field mapping is honest: ref/alt/pos come straight from the call, QUAL is derived from
    the real depth/allele-fraction, FILTER is PASS only when an orthogonal caller agreed, and
    INFO carries the real per-variant metrics (DP/AF/type) plus any annotation fields the
    later stages attached (gene / consequence / gnomAD AF / ClinVar).
    """
    header = [
        "##fileformat=VCFv4.2",
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FILTER=<ID=LowQual,Description="Failed quality or concordance filters">',
        '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total read depth">',
        '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele fraction">',
        '##INFO=<ID=VT,Number=1,Type=String,Description="Variant type">',
        '##INFO=<ID=GENE,Number=1,Type=String,Description="Annotated gene">',
        '##INFO=<ID=CONSEQUENCE,Number=1,Type=String,Description="Consequence">',
        '##INFO=<ID=IMPACT,Number=1,Type=String,Description="Predicted impact">',
        '##INFO=<ID=GNOMAD_AF,Number=1,Type=Float,Description="gnomAD allele frequency">',
        '##INFO=<ID=CLINVAR,Number=1,Type=String,Description="ClinVar significance">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
    ]
    rows: list[str] = []
    for v in variants:
        chrom = v.get("chrom", "chr1")
        pos = int(v.get("pos", 0))
        ref = v.get("ref") or "N"
        alt = v.get("alt") or "N"
        dp = v.get("dp")
        af = v.get("af")
        qual = _vcf_qual(af, dp)
        concordant = v.get("concordant", False)
        filt = "PASS" if concordant else "LowQual"
        info = _vcf_info(v)
        rows.append(f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t{qual}\t{filt}\t{info}")
    return "\n".join(header + rows) + "\n"


def build_visualization(state: dict) -> dict:
    """Extract IGV-ready SAM/VCF text (and a default locus) from the final pipeline state."""
    records = state.get("aligned_records") or []
    variants = _best_variants(state)
    sam = records_to_sam(records)
    vcf = variants_to_vcf(variants)

    locus = None
    for v in variants:
        if v.get("chrom") and v.get("pos"):
            locus = f"{v['chrom']}:{max(1, int(v['pos']) - 200)}-{int(v['pos']) + 200}"
            break
    if locus is None and records:
        mapped = [r for r in records if not r.get("is_unmapped") and r.get("pos")]
        if mapped:
            rname = mapped[0].get("rname", "chr1")
            min_p = min(r.get("pos", 1) for r in mapped)
            max_p = max(r.get("pos", 1) + _cigar_len(r.get("cigar", "")) for r in mapped)
            locus = f"{rname}:{min_p}-{max_p}"

    return {
        "sam": sam,
        "vcf": vcf,
        "locus": locus,
        "n_reads": len(records),
        "n_mapped": sum(1 for r in records if not r.get("is_unmapped")),
        "n_variants": len(variants),
    }


def _best_variants(state: dict) -> list[dict]:
    """Resolve the most-annotated variant set present in pipeline state (real, not fabricated)."""
    variants = state.get("variants", {})
    order = [
        ("prioritized", "variants"),
        ("knowledge", "variants"),
        ("filtered", "variants"),
        ("qc", "variants"),
        ("normalized", None),
        ("call", "variants"),
    ]
    for block, key in order:
        node = variants.get(block)
        if not node:
            continue
        cand = node.get(key) if key else node
        if isinstance(cand, list) and cand:
            return cand
    # top-level fallback: a bare list keyed under state["variants"]
    if isinstance(variants, list):
        return variants
    return []


def _cigar_len(cigar: str) -> int:
    import re
    return sum(int(n) for n in re.findall(r"\d+", cigar)) if cigar else 0


def _vcf_qual(af, dp) -> str:
    af = af if isinstance(af, (int, float)) else 0.0
    dp = dp if isinstance(dp, (int, float)) else 0
    if dp > 0:
        return f"{min(999, round(af * dp * 2, 1))}"
    return "."


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if v is None:
        return ""
    return str(v)


def _vcf_info(v: dict) -> str:
    parts = []
    if v.get("dp") is not None:
        parts.append(f"DP={v['dp']}")
    if v.get("af") is not None:
        parts.append(f"AF={_fmt(v['af'])}")
    if v.get("type"):
        parts.append(f"VT={v['type']}")
    for k in ("gene", "consequence", "impact", "clinvar", "significance"):
        val = v.get(k)
        if val:
            up = k.upper()
            if up == "SIGNIFICANCE":
                up = "CLINVAR"
            parts.append(f"{up}={val}")
    if v.get("gnomad_af") is not None:
        parts.append(f"GNOMAD_AF={_fmt(v['gnomad_af'])}")
    return ";".join(parts) if parts else "."
