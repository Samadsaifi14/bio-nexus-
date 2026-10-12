from __future__ import annotations

import random

import pytest
from Bio.Seq import Seq


@pytest.mark.parametrize("seq_type,alphabet", [("dna", "ACGT"), ("rna", "ACGU")])
def test_sequence_utilities_randomized_reverse_complement_against_biopython(seq_type: str, alphabet: str):
    """1,000 seeded sequences per nucleotide alphabet against Biopython."""
    from app.tools.sequence_utilities import reverse_complement_sequence

    rng = random.Random(20260917 if seq_type == "dna" else 20260918)
    for _ in range(1000):
        length = rng.randint(1, 400)
        sequence = "".join(rng.choice(alphabet) for _ in range(length))
        observed = reverse_complement_sequence(sequence, seq_type)
        expected = str(Seq(sequence).reverse_complement() if seq_type == "dna" else Seq(sequence).reverse_complement_rna())
        assert observed == expected


def test_sequence_utilities_randomized_selected_frame_translation_against_biopython():
    from app.tools.sequence_utilities import translate_selected_frame

    rng = random.Random(20260919)
    for _ in range(1000):
        length = rng.randint(3, 600)
        sequence = "".join(rng.choice("ACGT") for _ in range(length))
        for frame in (1, 2, 3, -1, -2, -3):
            source = Seq(sequence) if frame > 0 else Seq(sequence).reverse_complement()
            offset = abs(frame) - 1
            usable = len(source[offset:]) - (len(source[offset:]) % 3)
            expected = str(source[offset:offset + usable].translate()) if usable else ""
            observed = translate_selected_frame(sequence, seq_type="dna", frame=frame)["protein"]
            assert observed == expected


def test_sequence_utilities_report_invalid_character_position():
    from app.tools.sequence_utilities import SequenceUtilitiesError, clean_sequence

    sequence = "ACGT" * 43 + "!" + "ACGT"
    with pytest.raises(SequenceUtilitiesError, match=r"position 173"):
        clean_sequence(sequence, "dna")


def test_translate_cds_does_not_search_for_first_atg():
    from app.tools.sequence_utilities import translate_cds

    # A historical browser implementation searched forward for the first ATG.
    # Declared-CDS translation now begins at the explicitly selected frame.
    result = translate_cds("CCCATGAAATAA", seq_type="dna", frame=1)
    assert result["protein"] == "PMK"
    assert result["starts_with_m"] is False


def test_pairwise_local_coordinates_are_original_input_coordinates():
    from app.tools.pairwise_alignment import pairwise_align

    query = "WWWWWWWWWWMKTLLVWWWWW"
    subject = "DDDDDDDDDDMKTLLVDDDDD"
    result = pairwise_align(query, subject, mode="local", matrix="blosum62", open_gap_score=-10, extend_gap_score=-1)

    assert result["query_start"] == 11
    assert result["query_end"] == 16
    assert result["hit_start"] == 11
    assert result["hit_end"] == 16
    assert result["aligned_query"] == "MKTLLV"
    assert result["aligned_hit"] == "MKTLLV"
    assert result["identity"] == 6
    assert result["similarity"] == 6
    assert result["mismatches"] == 0
    assert result["matrix"] == "blosum62"
    assert result["open_gap_score"] == -10.0
    assert result["extend_gap_score"] == -1.0


def test_pairwise_does_not_silently_delete_invalid_characters():
    from app.tools.pairwise_alignment import PairwiseAlignError, pairwise_align

    with pytest.raises(PairwiseAlignError, match="invalid character"):
        pairwise_align("MKT!LLV", "MKTLLV", mode="local")


@pytest.mark.asyncio
async def test_castp_request_never_substitutes_fpocket_or_heuristic():
    from app.tools.castp import _analyze_pockets

    result = await _analyze_pockets("", "custom", 1.4, method="castp")
    assert result["status"] == "FAILED"
    assert result["method"] == "CASTp"
    assert result["fallback_used"] is False
    assert result["pockets"] == []
    assert result["validation"]["castp_values_substituted"] is False


@pytest.mark.asyncio
async def test_fpocket_unavailable_fails_without_heuristic(monkeypatch):
    import app.tools.castp as pockets

    monkeypatch.setattr(pockets, "FPOCKET_BIN", "/definitely/not/fpocket")
    monkeypatch.setattr(pockets.shutil, "which", lambda _name: None)
    result = await pockets._analyze_pockets("", "custom", 1.4, method="fpocket")
    assert result["status"] == "FAILED"
    assert result["method"] == "fpocket"
    assert result["pockets"] == []
    assert result["validation"]["castp_values_substituted"] is False
    assert "no heuristic" in result["validation"]["reason"].lower()


def test_exploratory_pocket_method_is_labelled_heuristic():
    from app.tools.castp import _analyze_pockets_sasa_sync

    pdb = "\n".join([
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C",
        "ATOM      2  CA  GLY A   2       3.800   0.000   0.000  1.00 20.00           C",
        "ATOM      3  CA  SER A   3       7.600   0.000   0.000  1.00 20.00           C",
        "ATOM      4  CA  LEU A   4      11.400   0.000   0.000  1.00 20.00           C",
        "ATOM      5  CA  VAL A   5      15.200   0.000   0.000  1.00 20.00           C",
        "END",
    ]) + "\n"
    result = _analyze_pockets_sasa_sync(pdb, "custom", 1.4)
    assert result["status"] == "VALID"
    assert result["method"] == "BioNexus exploratory SASA heuristic"
    assert result["evidence_class"] == "Heuristic"
    assert result["validation"]["not_castp"] is True
    assert result["validation"]["not_fpocket"] is True
