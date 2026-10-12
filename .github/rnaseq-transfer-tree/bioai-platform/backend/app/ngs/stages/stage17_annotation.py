"""Stage 17 — transcript-grounded variant consequence annotation.

This module is intentionally conservative. It annotates variants only against a
transcript table supplied to the run; it does not silently invent genes,
transcripts, or consequences from a remote database.

Expected transcript shape (1-based inclusive genomic coordinates)::

    {
      "gene": "BRCA1",
      "transcript_id": "ENST...",
      "source": "GENCODE release ...",
      "chrom": "chr17",
      "strand": "+",
      "cds_offset": 41197902,
      "exons": [{"start": ..., "end": ...}],
      "cds_seq": "ATGGAT..."
    }

`cds_offset` is the genomic coordinate of the first base represented by
`cds_seq` in transcript orientation: the lowest coding genomic coordinate for
`+` strand and the highest coding genomic coordinate for `-` strand.

Research-grade changes in v0.2.0:

- CDS position is computed across spliced exons rather than by raw genomic
  subtraction through introns.
- Negative-strand alleles are reverse-complemented before codon substitution.
- Coding indels are distinguished as in-frame vs frameshift using length delta.
- Reference/coding-sequence mismatches are surfaced explicitly instead of being
  silently translated.
- Annotation method, transcript identity and transcript source are carried in
  every annotation record for provenance.

This is a lightweight consequence engine, not a replacement for VEP/snpEff.
BBS-1 benchmarks it only on transcript/reference definitions that can be
matched exactly to the external reference annotator.
"""

from __future__ import annotations

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule

CODON = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "TCT": "S", "TCC": "S",
    "TCA": "S", "TCG": "S", "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CTT": "L", "CTC": "L",
    "CTA": "L", "CTG": "L", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q", "CGT": "R", "CGC": "R",
    "CGA": "R", "CGG": "R", "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "AAT": "N", "AAC": "N",
    "AAA": "K", "AAG": "K", "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "G",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V", "GCT": "A", "GCC": "A",
    "GCA": "A", "GCG": "A", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Correct a typo defensively if this table is ever edited around the dense literal above.
CODON["AGG"] = "R"

SPLICE_WINDOW = 2
ANNOTATION_VERSION = "0.2.0"
ANNOTATION_METHOD = "bionexus-transcript-coordinate"


def _revcomp(sequence: str) -> str:
    return sequence.upper().translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


def _annotation_provenance(tx: dict | None) -> dict:
    tx = tx or {}
    return {
        "annotation_method": ANNOTATION_METHOD,
        "annotation_version": ANNOTATION_VERSION,
        "transcript_id": tx.get("transcript_id"),
        "transcript_source": tx.get("source") or "user_supplied_transcript_table",
    }


def _with_annotation(var: dict, tx: dict | None = None, **fields) -> dict:
    return {
        **var,
        "annotation": {
            **fields,
            **_annotation_provenance(tx),
        },
    }


def _sorted_exons(tx: dict) -> list[dict]:
    return sorted(tx.get("exons", []), key=lambda exon: (exon["start"], exon["end"]))


def _genomic_to_cds_position(pos: int, tx: dict) -> int | None:
    """Map one exonic genomic coordinate to a 1-based spliced CDS position.

    The calculation walks only exonic bases between `cds_offset` and `pos`, so
    intron length cannot shift codon phase. Returns None when either coordinate
    is not represented by an exon or when the requested position lies before
    the coding start in transcript orientation.
    """
    cds_offset = tx.get("cds_offset")
    if cds_offset is None:
        return None

    exons = _sorted_exons(tx)
    if not exons:
        return None

    strand = tx.get("strand", "+")
    if strand not in {"+", "-"}:
        return None

    if not any(exon["start"] <= pos <= exon["end"] for exon in exons):
        return None
    if not any(exon["start"] <= cds_offset <= exon["end"] for exon in exons):
        return None

    if strand == "+":
        if pos < cds_offset:
            return None
        ordered = exons
        total = 0
        started = False
        for exon in ordered:
            start, end = exon["start"], exon["end"]
            if not started:
                if start <= cds_offset <= end:
                    started = True
                    segment_start = cds_offset
                else:
                    continue
            else:
                segment_start = start

            if segment_start <= pos <= end:
                return total + (pos - segment_start) + 1
            total += end - segment_start + 1
        return None

    # Negative strand: transcript runs from high genomic coordinates to low.
    if pos > cds_offset:
        return None
    ordered = list(reversed(exons))
    total = 0
    started = False
    for exon in ordered:
        start, end = exon["start"], exon["end"]
        if not started:
            if start <= cds_offset <= end:
                started = True
                segment_high = cds_offset
            else:
                continue
        else:
            segment_high = end

        if start <= pos <= segment_high:
            return total + (segment_high - pos) + 1
        total += segment_high - start + 1
    return None


def _select_transcript(var: dict, transcripts: list[dict]) -> dict | None:
    """Select a covering transcript deterministically.

    If multiple transcripts cover the site, prefer a transcript explicitly
    marked canonical, then one with a CDS sequence, then lexical transcript ID.
    The chosen transcript ID is exposed in output so this decision is auditable.
    """
    chrom = var.get("chrom")
    pos = var.get("pos")
    candidates: list[dict] = []
    for tx in transcripts:
        if tx.get("chrom") != chrom:
            continue
        exons = _sorted_exons(tx)
        if not exons:
            continue
        body_lo = min(exon["start"] for exon in exons)
        body_hi = max(exon["end"] for exon in exons)
        if body_lo <= pos <= body_hi:
            candidates.append(tx)

    if not candidates:
        return None

    candidates.sort(
        key=lambda tx: (
            not bool(tx.get("canonical")),
            not bool(tx.get("cds_seq")),
            str(tx.get("transcript_id") or ""),
        )
    )
    return candidates[0]


def annotate_variant(var: dict, transcripts: list[dict]) -> dict:
    """Annotate one variant against the supplied transcript definitions."""
    pos = var.get("pos")
    ref = (var.get("ref") or "").upper()
    alt = (var.get("alt") or "").upper()
    if pos is None:
        return _with_annotation(var, error="missing position", consequence="unannotated")

    tx = _select_transcript(var, transcripts)
    if tx is None:
        return _with_annotation(
            var,
            gene=None,
            consequence="intergenic",
            impact="MODIFIER",
            region="intergenic",
        )

    gene = tx.get("gene")
    exons = _sorted_exons(tx)
    cds_seq = (tx.get("cds_seq") or "").upper()
    strand = tx.get("strand", "+")

    in_exon = any(exon["start"] <= pos <= exon["end"] for exon in exons)
    if not in_exon:
        near = any(
            abs(pos - exon["start"]) <= SPLICE_WINDOW
            or abs(pos - exon["end"]) <= SPLICE_WINDOW
            for exon in exons
        )
        consequence = "splice_region" if near else "intronic"
        return _with_annotation(
            var,
            tx,
            gene=gene,
            consequence=consequence,
            impact="LOW" if consequence == "splice_region" else "MODIFIER",
            region=consequence,
        )

    if cds_seq and tx.get("cds_offset") is not None:
        cds_pos = _genomic_to_cds_position(pos, tx)
        if cds_pos is not None and 1 <= cds_pos <= len(cds_seq):
            return _annotate_coding(var, tx, cds_seq, cds_pos, ref, alt, gene, strand)
        return _with_annotation(
            var,
            tx,
            gene=gene,
            consequence="exon_utr",
            impact="MODIFIER",
            region="UTR",
        )

    return _with_annotation(
        var,
        tx,
        gene=gene,
        consequence="exonic_unresolved_cds",
        impact="MODIFIER",
        region="exon",
        warning="Transcript lacks cds_seq and/or cds_offset; coding consequence not inferred.",
    )


def _annotate_coding(
    var: dict,
    tx: dict,
    cds_seq: str,
    cds_pos: int,
    ref: str,
    alt: str,
    gene: str | None,
    strand: str,
) -> dict:
    oriented_ref = _revcomp(ref) if strand == "-" else ref
    oriented_alt = _revcomp(alt) if strand == "-" else alt

    # SNV
    if oriented_ref and oriented_alt and len(oriented_ref) == 1 and len(oriented_alt) == 1:
        sequence_ref = cds_seq[cds_pos - 1]
        if sequence_ref not in {"N", oriented_ref} and oriented_ref != "N":
            return _with_annotation(
                var,
                tx,
                gene=gene,
                consequence="reference_mismatch",
                impact="UNKNOWN",
                region="coding",
                cds_pos=cds_pos,
                expected_ref=sequence_ref,
                provided_ref=oriented_ref,
                warning="Variant reference allele does not match supplied cds_seq in transcript orientation.",
            )

        codon_index = cds_pos - 1
        codon_start = (codon_index // 3) * 3
        if codon_start + 3 <= len(cds_seq):
            codon_ref = cds_seq[codon_start:codon_start + 3]
            codon_alt_list = list(codon_ref)
            codon_alt_list[codon_index - codon_start] = oriented_alt
            codon_alt = "".join(codon_alt_list)
            aa_ref = CODON.get(codon_ref, "?")
            aa_alt = CODON.get(codon_alt, "?")

            if aa_ref == "?" or aa_alt == "?":
                consequence, impact = "coding_unresolved", "UNKNOWN"
            elif aa_alt == aa_ref:
                consequence, impact = "synonymous", "LOW"
            elif aa_alt == "*":
                consequence, impact = "nonsense", "HIGH"
            elif aa_ref == "*" and aa_alt != "*":
                consequence, impact = "stop_lost", "HIGH"
            else:
                consequence, impact = "missense", "MODERATE"

            return _with_annotation(
                var,
                tx,
                gene=gene,
                consequence=consequence,
                impact=impact,
                region="coding",
                feature=tx.get("transcript_id") or gene,
                cds_pos=cds_pos,
                aa_ref=aa_ref,
                aa_alt=aa_alt,
                codon_ref=codon_ref,
                codon_alt=codon_alt,
                oriented_ref=oriented_ref,
                oriented_alt=oriented_alt,
            )

        return _with_annotation(
            var,
            tx,
            gene=gene,
            consequence="coding_unresolved",
            impact="UNKNOWN",
            region="coding",
            cds_pos=cds_pos,
            warning="Codon extends beyond supplied cds_seq.",
        )

    # Coding indel/MNV. We do not pretend to reconstruct a full HGVS consequence
    # here; frame preservation is the defensible local property available from
    # allele lengths.
    if oriented_ref or oriented_alt:
        delta = len(oriented_alt) - len(oriented_ref)
        if delta == 0:
            consequence, impact = "coding_mnv", "MODERATE"
        elif delta % 3 == 0:
            consequence, impact = "inframe_indel", "MODERATE"
        else:
            consequence, impact = "frameshift", "HIGH"
        return _with_annotation(
            var,
            tx,
            gene=gene,
            consequence=consequence,
            impact=impact,
            region="coding",
            cds_pos=cds_pos,
            length_delta=delta,
            oriented_ref=oriented_ref,
            oriented_alt=oriented_alt,
        )

    return _with_annotation(
        var,
        tx,
        gene=gene,
        consequence="coding_unresolved",
        impact="UNKNOWN",
        region="coding",
        cds_pos=cds_pos,
        warning="Reference and alternate alleles are missing.",
    )


def run_annotation(variants: list[dict], transcripts: list[dict]) -> dict:
    annotated = [annotate_variant(variant, transcripts) for variant in variants]
    by_consequence: dict[str, int] = {}
    for variant in annotated:
        consequence = variant.get("annotation", {}).get("consequence") or "unannotated"
        by_consequence[consequence] = by_consequence.get(consequence, 0) + 1
    return {
        "variants": annotated,
        "summary": by_consequence,
        "n_annotated": len(annotated),
        "annotation_method": ANNOTATION_METHOD,
        "annotation_version": ANNOTATION_VERSION,
        "transcript_table_supplied": bool(transcripts),
        "scope_note": (
            "Consequences are computed only from the supplied transcript definitions. "
            "This lightweight engine is not a replacement for VEP/snpEff."
        ),
    }


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
        version=ANNOTATION_VERSION,
        inputs=["final_variants", "transcripts"],
        outputs=["annotated_variants"],
        rules=[
            ThresholdRule(
                name="annotation_completed",
                metric="annotation_completed",
                evaluate=lambda value: _pct_rule(value, 100, 100),
                expectation="completed",
            ),
        ],
        fail_blocks=False,
        run=_stage17_run,
    )


def _pct_rule(value, ok, warn):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if value >= ok:
        return QcStatus.PASS
    if value >= warn:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_annotation_stage(variants: list[dict], transcripts: list[dict]) -> dict:
    from app.ngs.contracts import QcResult, apply_rules

    report = run_annotation(variants, transcripts)
    contract = stage17_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"annotation_completed": 100.0}),
        fail_blocks=False,
    )
    return {
        "result": {
            "step": "annotation",
            "qc": result.to_dict(),
            "decision": result.decision.value,
            "data": report["summary"],
        },
        "summary": {
            "status": result.status.value,
            "decision": result.decision.value,
            "consequence_counts": report["summary"],
            "variants": report["variants"],
            "annotation_method": report["annotation_method"],
            "annotation_version": report["annotation_version"],
        },
        "variants": report["variants"],
    }
