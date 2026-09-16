"""Publication audit: randomized and known-answer pairwise-alignment checks."""

from __future__ import annotations

import random

import pytest

from app.tools.pairwise_alignment import PairwiseAlignError, pairwise_align


SEED = 20260916
AA = "ACDEFGHIKLMNPQRSTVWY"


def test_random_identical_proteins_are_100_percent_identical_in_global_and_local_modes():
    rng = random.Random(SEED)
    for _ in range(75):
        n = rng.randint(5, 100)
        sequence = "".join(rng.choice(AA) for _ in range(n))
        for mode in ("global", "local"):
            result = pairwise_align(sequence, sequence, mode=mode)
            assert result["identity"] == n
            assert result["alignment_length"] == n
            assert result["pct_identity"] == 100.0
            assert result["gaps_total"] == 0
            assert result["query_start"] == 1
            assert result["query_end"] == n
            assert result["hit_start"] == 1
            assert result["hit_end"] == n


def test_local_alignment_reports_original_coordinates_for_internal_matches():
    rng = random.Random(SEED + 1)
    flank_alphabet = "ACDEFGHIKLMNPQRSTVY"  # excludes W
    motif = "WWWWWW"
    for _ in range(40):
        left_len = rng.randint(1, 35)
        right_len = rng.randint(1, 35)
        left = "".join(rng.choice(flank_alphabet) for _ in range(left_len))
        right = "".join(rng.choice(flank_alphabet) for _ in range(right_len))
        query = left + motif + right
        result = pairwise_align(query, motif, mode="local")
        assert result["aligned_query"] == motif
        assert result["aligned_hit"] == motif
        assert result["query_start"] == left_len + 1
        assert result["query_end"] == left_len + len(motif)
        assert result["hit_start"] == 1
        assert result["hit_end"] == len(motif)


def test_non_matrix_residues_are_rejected_instead_of_becoming_server_errors():
    for bad in ("MOU", "PEPTJDE", "ABC123O"):
        with pytest.raises(PairwiseAlignError):
            pairwise_align(bad, "ACDEFG")


def test_positive_gap_rewards_are_rejected_as_invalid_alignment_parameters():
    with pytest.raises(PairwiseAlignError):
        pairwise_align("ACDEFG", "ACDEFG", open_gap_score=5)
    with pytest.raises(PairwiseAlignError):
        pairwise_align("ACDEFG", "ACDEFG", extend_gap_score=1)


def test_random_global_alignment_coordinate_and_count_invariants():
    rng = random.Random(SEED + 2)
    for _ in range(75):
        a = "".join(rng.choice(AA) for _ in range(rng.randint(5, 80)))
        b = "".join(rng.choice(AA) for _ in range(rng.randint(5, 80)))
        result = pairwise_align(a, b, mode="global")
        assert len(result["aligned_query"]) == len(result["aligned_hit"]) == result["alignment_length"]
        assert result["identity"] <= result["alignment_length"]
        assert 0.0 <= result["pct_identity"] <= 100.0
        assert result["query_start"] == 1
        assert result["query_end"] == len(a)
        assert result["hit_start"] == 1
        assert result["hit_end"] == len(b)
        assert result["gaps_total"] == result["aligned_query"].count("-") + result["aligned_hit"].count("-")
