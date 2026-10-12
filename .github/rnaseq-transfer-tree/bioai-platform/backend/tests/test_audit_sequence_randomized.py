"""Publication audit: independent randomized checks for sequence utilities.

These tests deliberately use independent Biopython implementations as the
reference rather than reusing BioNexus helper functions.  The pseudo-random
inputs are deterministic so a failure can be reproduced exactly.
"""

from __future__ import annotations

import random

import pytest
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction, molecular_weight

from app.services.sequence_utils import detect_sequence_type
from app.tools.sequence_utilities import analyze_sequence, clean_sequence


SEED = 20260916


def _dna_cases(n: int = 100):
    rng = random.Random(SEED)
    for _ in range(n):
        length = rng.randint(1, 300)
        yield "".join(rng.choice("ACGT") for _ in range(length))


def _rna_cases(n: int = 100):
    rng = random.Random(SEED + 1)
    for _ in range(n):
        length = rng.randint(1, 300)
        yield "".join(rng.choice("ACGU") for _ in range(length))


def test_random_dna_metrics_match_independent_biopython_reference():
    for sequence in _dna_cases():
        observed = analyze_sequence(sequence, "dna")
        assert observed["length"] == len(sequence)
        assert observed["gc_content"] == pytest.approx(gc_fraction(sequence) * 100.0, abs=0.05)
        assert observed["reverse_complement"] == str(Seq(sequence).reverse_complement())
        assert observed["molecular_weight"] == pytest.approx(
            molecular_weight(sequence, seq_type="DNA", double_stranded=False, circular=False),
            abs=0.05,
        )


def test_random_rna_metrics_match_independent_biopython_reference():
    for sequence in _rna_cases():
        observed = analyze_sequence(sequence, "rna")
        assert observed["length"] == len(sequence)
        assert observed["gc_content"] == pytest.approx(gc_fraction(sequence) * 100.0, abs=0.05)
        assert observed["reverse_complement"] == str(Seq(sequence).reverse_complement_rna())
        assert observed["molecular_weight"] == pytest.approx(
            molecular_weight(sequence, seq_type="RNA", double_stranded=False, circular=False),
            abs=0.05,
        )


def test_rna_cleaning_does_not_silently_convert_u_to_t():
    assert clean_sequence("AUGCUU", "rna") == "AUGCUU"


def test_iupac_dna_reverse_complement_is_iupac_aware_and_mass_is_not_fabricated():
    sequence = "ACGTRYSWKMBDHVN"
    observed = analyze_sequence(sequence, "dna")
    assert observed["reverse_complement"] == str(Seq(sequence).reverse_complement())
    assert observed["molecular_weight"] is None
    assert any("molecular weight" in issue.lower() and "ambiguous" in issue.lower() for issue in observed["issues"])


def test_iupac_rna_reverse_complement_is_iupac_aware_and_mass_is_not_fabricated():
    sequence = "ACGURYSWKMBDHVN"
    observed = analyze_sequence(sequence, "rna")
    assert observed["reverse_complement"] == str(Seq(sequence).reverse_complement_rna())
    assert observed["molecular_weight"] is None
    assert any("molecular weight" in issue.lower() and "ambiguous" in issue.lower() for issue in observed["issues"])


def test_auto_detection_handles_iupac_when_nucleotide_identity_is_explicit():
    assert detect_sequence_type("ACGTRY") == "dna"
    assert detect_sequence_type("ACGURY") == "rna"


def test_mixed_thymine_and_uracil_is_not_silently_classified_as_protein():
    assert detect_sequence_type("ACGTUACG") == "unknown"
