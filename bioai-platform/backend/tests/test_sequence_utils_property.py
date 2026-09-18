"""Randomized/property tests for the sequence-utilities toolkit against Biopython.

Each metric is cross-checked on many seeded random inputs so the shared backend
sequence library provably matches the reference implementation (Biopython):

  * reverse complement (IUPAC-aware, ambiguous letters)
  * transcription (DNA -> RNA copy)
  * GC content
  * six-frame translation (frames 1-3 forward, 4-6 reverse)
  * ssDNA / protein molecular weight conventions
  * strict invalid-character position reporting
"""

import random

import pytest
from Bio.Seq import Seq
from Bio.SeqUtils import molecular_weight
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from app.tools.sequence_utilities import _nucleotide_mw, analyze_sequence

pytestmark = pytest.mark.filterwarnings("ignore::Bio.BiopythonWarning")  # partial codon in random len


def _gc_reference(s: str) -> float:
    return round((s.count("G") + s.count("C")) / len(s) * 100.0, 1)

_rng = random.Random(20260918)

DNA = "ACGT"
IUPAC_DNA = "ACGTRYSWKMBDHVN"
RNA = "ACGU"
PROT = "ACDEFGHIKLMNPQRSTVWY"


def rand_seq(alphabet: str, lo: int = 25, hi: int = 180) -> str:
    n = _rng.randint(lo, hi)
    return "".join(_rng.choice(alphabet) for _ in range(n))


class TestReverseComplement:
    def test_matches_biopython_across_random_iupac(self):
        for _ in range(30):
            s = rand_seq(IUPAC_DNA)
            assert analyze_sequence(s, seq_type="dna")["reverse_complement"] == str(Seq(s).reverse_complement())

    def test_revcomp_is_involution(self):
        for _ in range(15):
            s = rand_seq(DNA)
            rc = analyze_sequence(s, seq_type="dna")["reverse_complement"]
            assert analyze_sequence(rc, seq_type="dna")["reverse_complement"] == s


class TestTranscription:
    def test_matches_biopython_transcribe(self):
        for _ in range(30):
            s = rand_seq(DNA)
            assert analyze_sequence(s, seq_type="dna")["transcription"] == str(Seq(s).transcribe())

    def test_transcript_contains_no_t(self):
        for _ in range(15):
            s = rand_seq(DNA)
            tr = analyze_sequence(s, seq_type="dna")["transcription"]
            assert "T" not in tr and len(tr) == len(s)


class TestGcContent:
    def test_matches_canonical_definition(self):
        # Cross-check against the canonical GC formula (G+C)/length, the same
        # definition Biopython's classic Bio.SeqUtils.GC function used.
        for _ in range(30):
            s = rand_seq(DNA)
            assert analyze_sequence(s, seq_type="dna")["gc_content"] == pytest.approx(_gc_reference(s), abs=0.05)

    def test_gc_bounds(self):
        for _ in range(15):
            s = rand_seq(DNA)
            gc = analyze_sequence(s, seq_type="dna")["gc_content"]
            assert 0.0 <= gc <= 100.0


class TestSixFrameTranslation:
    def test_first_frame_matches_biopython(self):
        for _ in range(30):
            s = rand_seq(DNA)
            frames = analyze_sequence(s, seq_type="dna")["translation"]["frames"]
            assert frames["1"] == str(Seq(s).translate())

    def test_fourth_frame_is_reverse_strand_translation(self):
        for _ in range(30):
            s = rand_seq(DNA)
            frames = analyze_sequence(s, seq_type="dna")["translation"]["frames"]
            rc = str(Seq(s).reverse_complement())
            assert frames["4"] == str(Seq(rc).translate())

    def test_all_six_frames_present(self):
        res = analyze_sequence("ATGCATTAACGTGCATGACCGTTACGAATGGC", seq_type="dna")
        assert set(res["translation"]["frames"].keys()) == {"1", "2", "3", "4", "5", "6"}
        assert res["translation"]["best"]["strand"] in ("forward", "reverse")

    def test_best_orf_coordinates_match_sequence_length(self):
        for _ in range(20):
            s = rand_seq(DNA)
            best = analyze_sequence(s, seq_type="dna")["translation"]["best"]
            if best:
                assert 1 <= best["start"] <= len(s)


class TestMolecularWeight:
    def test_ssdna_matches_biopython_convention(self):
        for _ in range(20):
            s = rand_seq(DNA)
            expected = sum(molecular_weight(b, seq_type="DNA") for b in s) - 18.02 * (len(s) - 1)
            assert _nucleotide_mw(s, "dna") == pytest.approx(expected, abs=0.05 * len(s) + 0.5)

    def test_protein_matches_biopython(self):
        for _ in range(20):
            s = rand_seq(PROT)
            assert analyze_sequence(s, seq_type="protein")["molecular_weight"] == pytest.approx(
                ProteinAnalysis(s).molecular_weight(), rel=1e-4
            )


class TestStrictInvalidCharacters:
    def test_positions_reported_in_alpha_body(self):
        # Z and X are not valid IUPAC-DNA letters; they sit at alpha-body
        # positions 4 and 5 of "ATGZXCATG".
        res = analyze_sequence("ATGZXCATG", seq_type="dna")
        assert res["length"] == len("ATGZXCATG") - 2
        issue = [i for i in res["issues"] if "Ignored invalid characters" in i]
        assert issue, res["issues"]
        assert "Z@position 4" in issue[0]
        assert "X@position 5" in issue[0]

    def test_mixed_rna_dna_reported_and_positions(self):
        # For RNA, T is not a valid base (only U); it is dropped with positions.
        res = analyze_sequence("AUCGT", seq_type="rna")
        issue = [i for i in res["issues"] if "Ignored invalid characters" in i]
        assert issue
        assert "T@position 5" in issue[0]
        assert res["length"] == 4