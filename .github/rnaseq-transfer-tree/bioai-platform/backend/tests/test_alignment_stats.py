"""Tests for the backend-emitted MSA column statistics.

The frontend renders these values verbatim; these tests pin the exact
scientific semantics: matched = invariant column, mismatched = variable
column with no gaps, gapped = column containing at least one gap.
All runs are offline.
"""

from app.tools.alignment_stats import alignment_stats, parse_aligned_fasta


class TestParseAlignedFasta:
    def test_returns_bodies_in_order(self):
        seqs = parse_aligned_fasta(">a\nAC-T\n>bb\nA-CT\n>c\nACT-")
        assert seqs == ["AC-T", "A-CT", "ACT-"]

    def test_ignores_whitespace_and_blank_lines(self):
        seqs = parse_aligned_fasta("\n>a\nA-C\nT\n   \n>b\nAC-\nT\n")
        assert seqs == ["A-CT", "AC-T"]

    def test_empty_input(self):
        assert parse_aligned_fasta("") == []
        assert parse_aligned_fasta(None) == []


class TestAlignmentStats:
    def test_identical_sequences(self):
        stats = alignment_stats(["ACDEFGHIK", "ACDEFGHIK"])
        assert stats["length"] == 9
        assert stats["matched"] == 9
        assert stats["mismatched"] == 0
        assert stats["gapped"] == 0
        assert stats["total_gaps"] == 0
        assert stats["identity_pct"] == 100.0

    def test_single_gap_columns(self):
        stats = alignment_stats(["AC-T", "A-CT"])
        assert stats["length"] == 4
        assert stats["matched"] == 2
        assert stats["gapped"] == 2
        assert stats["total_gaps"] == 2
        assert stats["mismatched"] == 0
        assert round(stats["identity_pct"], 1) == 50.0

    def test_mismatch_column_without_gaps(self):
        stats = alignment_stats(["ACD", "ACG"])
        assert stats["length"] == 3
        assert stats["matched"] == 2
        assert stats["mismatched"] == 1
        assert stats["gapped"] == 0

    def test_trailing_gap_collapsing(self):
        stats = alignment_stats(["AC-T", "A-CT", "ACT-"])
        assert stats["gapped"] == 3
        assert stats["matched"] == 1
        assert stats["mismatched"] == 0
        assert stats["total_gaps"] == 3

    def test_case_insensitive_matching(self):
        stats = alignment_stats(["ACD", "acd"])
        assert stats["matched"] == 3
        assert stats["identity_pct"] == 100.0

    def test_empty_and_ragged_input(self):
        empty = alignment_stats([])
        assert empty["length"] == 0 and empty["identity_pct"] == 0.0
        ragged = alignment_stats(["ACD", "AC"])
        assert ragged["length"] == 3
        assert ragged["gapped"] == 1