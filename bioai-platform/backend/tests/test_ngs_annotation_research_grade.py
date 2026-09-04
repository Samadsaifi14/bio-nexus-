"""Reference cases for the BBS-1 Stage-17 consequence engine."""

from app.ngs.stages.stage17_annotation import (
    _genomic_to_cds_position,
    annotate_variant,
    run_annotation,
)


def _plus_two_exon_tx():
    # Spliced CDS = ATG AAA GCT TTT = M K A F
    return {
        "gene": "TEST1",
        "transcript_id": "TX_PLUS",
        "source": "BBS1 synthetic transcript",
        "chrom": "chr1",
        "strand": "+",
        "canonical": True,
        "cds_offset": 100,
        "exons": [{"start": 100, "end": 105}, {"start": 200, "end": 205}],
        "cds_seq": "ATGAAAGCTTTT",
    }


def _minus_two_exon_tx():
    # Same transcript-oriented CDS. First CDS base is genomic position 305.
    return {
        "gene": "TEST2",
        "transcript_id": "TX_MINUS",
        "source": "BBS1 synthetic transcript",
        "chrom": "chr2",
        "strand": "-",
        "canonical": True,
        "cds_offset": 305,
        "exons": [{"start": 200, "end": 205}, {"start": 300, "end": 305}],
        "cds_seq": "ATGAAAGCTTTT",
    }


def test_spliced_plus_strand_position_skips_intron():
    tx = _plus_two_exon_tx()
    assert _genomic_to_cds_position(100, tx) == 1
    assert _genomic_to_cds_position(105, tx) == 6
    assert _genomic_to_cds_position(200, tx) == 7
    assert _genomic_to_cds_position(205, tx) == 12


def test_spliced_minus_strand_position_skips_intron():
    tx = _minus_two_exon_tx()
    assert _genomic_to_cds_position(305, tx) == 1
    assert _genomic_to_cds_position(300, tx) == 6
    assert _genomic_to_cds_position(205, tx) == 7
    assert _genomic_to_cds_position(200, tx) == 12


def test_plus_strand_missense_across_second_exon():
    tx = _plus_two_exon_tx()
    # CDS position 7 starts GCT. G->A gives ACT (Ala -> Thr).
    result = annotate_variant({"chrom": "chr1", "pos": 200, "ref": "G", "alt": "A"}, [tx])
    ann = result["annotation"]
    assert ann["cds_pos"] == 7
    assert ann["codon_ref"] == "GCT"
    assert ann["codon_alt"] == "ACT"
    assert ann["aa_ref"] == "A"
    assert ann["aa_alt"] == "T"
    assert ann["consequence"] == "missense"
    assert ann["transcript_id"] == "TX_PLUS"
    assert ann["transcript_source"] == "BBS1 synthetic transcript"


def test_negative_strand_allele_is_complemented_before_codon_edit():
    tx = _minus_two_exon_tx()
    # Genomic T>C at position 305 becomes transcript-oriented A>G at CDS pos 1.
    result = annotate_variant({"chrom": "chr2", "pos": 305, "ref": "T", "alt": "C"}, [tx])
    ann = result["annotation"]
    assert ann["cds_pos"] == 1
    assert ann["oriented_ref"] == "A"
    assert ann["oriented_alt"] == "G"
    assert ann["codon_ref"] == "ATG"
    assert ann["codon_alt"] == "GTG"
    assert ann["aa_ref"] == "M"
    assert ann["aa_alt"] == "V"
    assert ann["consequence"] == "missense"


def test_reference_mismatch_is_explicit():
    tx = _plus_two_exon_tx()
    result = annotate_variant({"chrom": "chr1", "pos": 100, "ref": "C", "alt": "T"}, [tx])
    ann = result["annotation"]
    assert ann["consequence"] == "reference_mismatch"
    assert ann["expected_ref"] == "A"
    assert ann["provided_ref"] == "C"
    assert ann["impact"] == "UNKNOWN"


def test_inframe_and_frameshift_indels_are_distinguished():
    tx = _plus_two_exon_tx()

    inframe = annotate_variant(
        {"chrom": "chr1", "pos": 100, "ref": "A", "alt": "ATGC"}, [tx]
    )["annotation"]
    frameshift = annotate_variant(
        {"chrom": "chr1", "pos": 100, "ref": "A", "alt": "AT"}, [tx]
    )["annotation"]

    assert inframe["length_delta"] == 3
    assert inframe["consequence"] == "inframe_indel"
    assert frameshift["length_delta"] == 1
    assert frameshift["consequence"] == "frameshift"


def test_report_exposes_annotation_scope_and_version():
    report = run_annotation([], [_plus_two_exon_tx()])
    assert report["annotation_method"] == "bionexus-transcript-coordinate"
    assert report["annotation_version"] == "0.2.0"
    assert report["transcript_table_supplied"] is True
    assert "not a replacement for VEP/snpEff" in report["scope_note"]
