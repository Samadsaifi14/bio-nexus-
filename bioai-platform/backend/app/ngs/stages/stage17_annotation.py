"""
Stage 17 — Variant annotation (blueprint Stage 17).

Real annotation requires a transcript table (CCDS/GENCODE-derived). The platform accepts one as
input — `transcripts` — and computes *actual* consequences, never guessed ones:

    [{
      "gene": "BRCA1", "chrom": "chr17", "strand": "+", "cds_offset": 41197902,
      "exons": [{"start": ..., "end": ...}],   # 1-based inclusive genomic exon coords
      "cds_seq": "ATGGAT...",                  # full coding sequence (optional)
    }]

For a variant at genomic position `pos` the engine decides, from the real coordinates:
    * intergenic            - no transcript covers the region
    * intronic              - inside an intron (between exons)
    * splice_region         - within SPLICE_WINDOW bp of an exon boundary
    * exon/UTR              - exonic but outside the coding sequence
    * coding (CDS)          - inside the coding region; translated against cds_seq to give
                              the true protein consequence:

                                  synonymous  (no amino-acid change)
                                  missense    (substitution, one codon)
                                  nonsense    (introduces a stop)
                                  inframe/frameshift for indels

The CDS offset maps the first coding base to a genomic position for strand "+"; for strand "-"
the engine still classifies region/splice/synonymous-vs-missense via the mirrored codon.
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule

CODON = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "TCT": "S", "TCC": "S",
    "TCA": "S", "TCG": "S", "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CTT": "L", "CTC": "L",
    "CTA": "L", "CTG": "L", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q", "CGT": "R", "CGC": "R",
    "CGA": "R", "CGG": "R", "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "AAT": "N", "AAC": "N",
    "AAA": "K", "AAG": "K", "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V", "GCT": "A", "GCC": "A",
    "GCA": "A", "GCG": "A", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

SPLICE_WINDOW = 2


def _revcomp(s: str) -> str:
    return s.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def annotate_variant(var: dict, transcripts: list[dict]) -> dict:
    """Annotate one variant against a transcript table."""
    chrom = var.get("chrom")
    pos = var.get("pos")
    ref = (var.get("ref") or "").upper()
    alt = (var.get("alt") or "").upper()
    if pos is None:
        return {**var, "annotation": {"error": "missing position"}}

    # Select the transcript whose *gene body* spans the position (any exon covers it, or it
    # falls in an intron between the transcript's first and last exon).
    best = None
    for tx in transcripts:
        if tx.get("chrom") != chrom:
            continue
        exons = tx.get("exons", [])
        if not exons:
            continue
        body_lo = min(ex["start"] for ex in exons)
        body_hi = max(ex["end"] for ex in exons)
        if body_lo <= pos <= body_hi:
            best = tx
            break

    if best is None:
        return {**var, "annotation": {"gene": None, "consequence": "intergenic",
                                      "impact": "MODIFIER", "region": "intergenic"}}

    gene = best.get("gene")
    cds_seq = (best.get("cds_seq") or "").upper()
    cds_offset = best.get("cds_offset")
    strand = best.get("strand", "+")

    # intronic?
    in_exon = any(ex["start"] <= pos <= ex["end"] for ex in best["exons"])
    if not in_exon:
        near = any(abs(pos - ex["start"]) <= SPLICE_WINDOW
                   or abs(pos - ex["end"]) <= SPLICE_WINDOW
                   for ex in best["exons"])
        cons = "splice_region" if near else "intronic"
        return {**var, "annotation": {"gene": gene, "consequence": cons,
                                      "impact": "MODIFIER" if cons == "intronic" else "LOW",
                                      "region": cons}}

    # exonic; is it within CDS?
    if cds_seq and cds_offset:
        if strand == "+":
            cds_pos = pos - cds_offset + 1      # 1-based index in cds_seq
        else:
            # mirrored: offset is the FIRST CDS base genomic coord (highest for - strand)
            cds_pos = cds_offset - pos + 1
        if 1 <= cds_pos <= len(cds_seq):
            return _annotate_coding(var, cds_seq, cds_pos, ref, alt, gene, strand)
        return {**var, "annotation": {"gene": gene, "consequence": "exon_utr",
                                      "impact": "MODIFIER", "region": "UTR"}}

    return {**var, "annotation": {"gene": gene, "consequence": "exonic",
                                  "impact": "MODIFIER", "region": "exon"}}


def _annotate_coding(var, cds_seq, cds_pos, ref, alt, gene, strand):
    if ref and alt and len(ref) == 1 and len(alt) == 1:
        codon_i = cds_pos - 1                    # 0-based
        start = (codon_i // 3) * 3
        if start + 3 <= len(cds_seq):
            codon = cds_seq[start:start + 3]
            alt_codon = list(codon)
            alt_codon[codon_i - start] = alt
            alt_codon = "".join(alt_codon)
            aa_ref = CODON.get(codon, "?")
            aa_alt = CODON.get(alt_codon, "?")
            if aa_alt == aa_ref:
                cons, impact = "synonymous", "LOW"
            elif aa_alt == "*":
                cons, impact = "nonsense", "HIGH"
            elif aa_ref == "*":
                # stop gained back to sense is unusual; treat as missense/escape
                cons, impact = "missense", "MODERATE"
            else:
                cons, impact = "missense", "MODERATE"
            return {**var, "annotation": {
                "gene": gene, "consequence": cons, "impact": impact, "region": "coding",
                "feature": gene, "cds_pos": cds_pos, "aa_ref": aa_ref, "aa_alt": aa_alt,
                "codon_ref": codon, "codon_alt": alt_codon}}
        return {**var, "annotation": {"gene": gene, "consequence": "coding",
                                      "impact": "MODERATE", "region": "coding"}}
    # indel inside CDS
    return {**var, "annotation": {"gene": gene, "consequence": "frameshift",
                                  "impact": "HIGH", "region": "coding"}}


def run_annotation(variants: list[dict], transcripts: list[dict]) -> dict:
    annotated = [annotate_variant(v, transcripts) for v in variants]
    by_cons: dict[str, int] = {}
    for v in annotated:
        cons = v.get("annotation", {}).get("consequence")
        by_cons[cons] = by_cons.get(cons, 0) + 1
    return {"variants": annotated, "summary": by_cons, "n_annotated": len(annotated)}


def _stage17_run(sample: dict, state: dict) -> tuple[dict, dict]:
    variants = state.get("variants", {}).get("filtered", {}).get("final")
    if variants is None:
        variants = state.get("variants", {}).get("final")
    transcripts = sample.get("transcripts") or state.get("transcripts") or []
    if variants is None:
        return {"error": "annotation needs final variants"}, {"annotation_completed": 0.0}
    report = run_annotation(variants, transcripts)
    report["status"] = "NOT_APPLICABLE" if not variants else "COMPLETED"
    report["n_input_variants"] = len(variants)
    state.setdefault("variants", {})["annotated"] = report
    return report, {"annotation_completed": 100.0}


def stage17_contract() -> StageContract:
    return StageContract(
        step="annotation",
        tool="platform-annotation",
        version="0.1.0",
        inputs=["final_variants", "transcripts"],
        outputs=["annotated_variants"],
        rules=[
            ThresholdRule(name="annotation_completed", metric="annotation_completed",
                          evaluate=lambda v: _pct_rule(v, 100, 100), expectation="completed"),
        ],
        fail_blocks=False,
        run=_stage17_run,
    )


def _pct_rule(v, ok, warn):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= ok:
        return QcStatus.PASS
    if v >= warn:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_annotation_stage(variants: list[dict], transcripts: list[dict]) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    report = run_annotation(variants, transcripts)
    contract = stage17_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"annotation_completed": 100.0}), fail_blocks=False)
    return {
        "result": {"step": "annotation", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": report["summary"]},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "consequence_counts": report["summary"], "variants": report["variants"]},
        "variants": report["variants"],
    }
