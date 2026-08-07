"""
Primer design QC + in-silico PCR validation.

Validates the oligo QC helpers and the /api/primers/* endpoints against
REAL biological reference data:

  * Human TP53 CDS (NM_000546.6, 393 aa / 1182 bp) — a canonical reference
    used for p53 mutation screening in the literature.
  * Known GC% / Tm arithmetic checks.
  * Known hairpin- and dimer-prone sequences.

The end-to-end test runs Primer3 on the TP53 CDS and verifies, for EVERY
returned primer pair, that the primers actually bind the reference template at
the reported coordinates and that the in-silico PCR amplicon matches the
reported product size.
"""

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.tools.oligo_qc import (
    reverse_complement,
    gc_content,
    salt_adjusted_tm,
    hairpin_analysis,
    dimer_analysis,
    in_silico_pcr,
    find_binding_sites,
    clean,
)

# Human TP53 CDS — NM_000546.6 (verified via NCBI efetch, 2026-08-07)
TP53_CDS = (
    "ATGGAGGAGCCGCAGTCAGATCCTAGCGTCGAGCCCCCTCTGAGTCAGGAAACATTTTCAGACCTATGGAAACTACTTCCTGAAAACAACGTTCTGTC"
    "CCCCTTGCCGTCCCAAGCAATGGATGATTTGATGCTGTCCCCGGACGATATTGAACAATGGTTCACTGAAGACCCAGGTCCAGATGAAGCTCCCAGAA"
    "TGCCAGAGGCTGCTCCCCCCGTGGCCCCTGCACCAGCAGCTCCTACACCGGCGGCCCCTGCACCAGCCCCCTCCTGGCCCCTGTCATCTTCTGTCCCT"
    "TCCCAGAAAACCTACCAGGGCAGCTACGGTTTCCGTCTGGGCTTCTTGCATTCTGGGACAGCCAAGTCTGTGACTTGCACGTACTCCCCTGCCCTCAAC"
    "AAGATGTTTTGCCAACTGGCCAAGACCTGCCCTGTGCAGCTGTGGGTTGATTCCACACCCCCGCCCGGCACCCGCGTCCGCGCCATGGCCATCTACAA"
    "GCAGTCACAGCACATGACGGAGGTTGTGAGGCGCTGCCCCCACCATGAGCGCTGCTCAGATAGCGATGGTCTGGCCCCTCCTCAGCATCTTATCCGAG"
    "TGGAAGGAAATTTGCGTGTGGAGTATTTGGATGACAGAAACACTTTTCGACATAGTGTGGTGGTGCCCTATGAGCCGCCTGAGGTTGGCTCTGACTGT"
    "ACCACCATCCACTACAACTACATGTGTAACAGTTCCTGCATGGGCGGCATGAACCGGAGGCCCATCCTCACCATCATCACACTGGAAGACTCCAGTGG"
    "TAATCTACTGGGACGGAACAGCTTTGAGGTGCGTGTTTGTGCCTGTCCTGGGAGAGACCGGCGCACAGAGGAAGAGAATCTCCGCAAGAAAGGGGAGC"
    "CTCACCACGAGCTGCCCCCAGGGAGCACTAAGCGAGCACTGCCCAACAACACCAGCTCCTCTCCCCAGCCAAAGAAGAAACCACTGGATGGAGAATAT"
    "TTCACCCTTCAGATCCGTGGGCGTGAGCGCTTCGAGATGTTCCGAGAGCTGAATGAGGCCTTGGAACTCAAGGATGCCCAGGCTGGGAAGGAGCCAGG"
    "GGGGAGCAGGGCTCACTCCAGCCACCTGAAGTCCAAAAAGGGTCAGTCTACCTCCCGCCATAAAAAACTCATGTTCAAGACAGAAGGGCCTGACTCAG"
    "ACTGA"
)


# ============================================================================
# 1. Core sequence math
# ============================================================================

class TestQueryBuilder:
    def test_plain_gene_translated_to_field_query(self):
        from app.routers.primers import _build_nucleotide_query
        assert _build_nucleotide_query("TP53 human") == "TP53[Gene Name] AND Homo sapiens[Organism]"
        assert _build_nucleotide_query("BRCA1") == "BRCA1[Gene Name]"
        assert _build_nucleotide_query("brca1 mouse") == "brca1[Gene Name] AND Mus musculus[Organism]"

    def test_existing_ncbi_query_passed_through(self):
        from app.routers.primers import _build_nucleotide_query
        assert _build_nucleotide_query("TP53[Gene Name] AND Homo sapiens[Organism]") == (
            "TP53[Gene Name] AND Homo sapiens[Organism]"
        )
        assert _build_nucleotide_query("") == ""

    def test_accession_query_uses_accn_field(self):
        from app.routers.primers import _build_nucleotide_query
        assert _build_nucleotide_query("NM_000546.6") == "NM_000546.6[ACCN]"
        assert _build_nucleotide_query("NG_017013") == "NG_017013[ACCN]"


class TestCoreMath:
    def test_reverse_complement(self):
        assert reverse_complement("ATGC") == "GCAT"
        assert reverse_complement("AATTCCGG") == "CCGGAATT"
        assert reverse_complement("ATGCN") == "NGCAT"
        # double application returns the original
        assert reverse_complement(reverse_complement("ATGCGTCAGTNN")) == "ATGCGTCAGTNN"

    def test_gc_content_known(self):
        # G=3, C=2 of 10 -> 50%
        assert gc_content("ATGCGTCAGT") == 50.0
        # pure GC -> 100%, pure AT -> 0%
        assert gc_content("GGGGCCCC") == 100.0
        assert gc_content("AAAAAATTTTTT") == 0.0

    def test_tm_sane_range_for_20mer(self):
        # Literature 20-mer primers generally sit at 45-65C; very GC-poor
        # oligos (25% GC) can legitimately dip to ~44C.
        for seq in ("ATGCGTCAGTATGACCTGTC", "CGGGTAGCTAGCATGCTAGG",
                    "GGGGCCCCAAAATTTTCCCC", "TAGTAGTAGTAGTAGTAGTA"):
            tm = salt_adjusted_tm(seq)
            assert 40.0 <= tm <= 75.0, f"Tm {tm} out of range for {seq}"
        # higher GC => higher Tm for equal length
        low_gc = salt_adjusted_tm("AAAAATTTTTAAAAATTTTT")
        high_gc = salt_adjusted_tm("GGGGGCCCCCGGGGGCCCCC")
        assert high_gc > low_gc

    def test_clean_strips_junk(self):
        assert clean(" atg-c\n gtc ") == "ATGCGTC"
        assert clean("Atg cgtAGt") == "ATGCGTAGT"


# ============================================================================
# 2. Hairpin / dimer detection on known sequences
# ============================================================================

class TestStructures:
    def test_hairpin_detected(self):
        # CCCC stem pairs with GGGG, loop TTT between -> hairpin.
        report = hairpin_analysis("AAAACCCCTTTGGGG")
        assert report["stem_length"] >= 4
        assert report["dg"] < 0
        assert report["risk"] in ("high", "medium", "low")

    def test_no_hairpin_on_plain_seq(self):
        # A 20-mer empirically verified to contain no inverted repeat of
        # >= 4 bases (so it cannot fold a stem-loop).
        report = hairpin_analysis("GCTAAAGACAATTACATAAC")
        assert report["risk"] == "none"

    def test_self_dimer_palindrome_is_high_risk(self):
        # GGGGGCCCCC is a palindrome; two copies dimerize fully.
        report = dimer_analysis("GGGGGCCCCC", "GGGGGCCCCC")
        assert report["dg"] <= -10
        assert report["risk"] == "high"
        assert report["involves_a3"]
        assert report["involves_b3"]

    def test_self_dimer_random_oligo_is_low_risk(self):
        # A random 20-mer empirically verified to contain no self-complementary
        # run of >= 4 canonical base pairs.
        report = dimer_analysis("TGGCATTTTTATTACACTCA", "TGGCATTTTTATTACACTCA")
        assert report["risk"] in ("none", "low")

    def test_hetero_dimer_complementary_pair(self):
        # A primer and its reverse complement anneal perfectly.
        fwd = "GTACCTAGCTAAGCT"
        rev = reverse_complement(fwd)
        report = dimer_analysis(fwd, rev)
        assert report["dg"] <= -10
        assert report["risk"] == "high"


# ============================================================================
# 3. In-silico PCR against the TP53 reference
# ============================================================================

class TestInsilicoPCR:
    def test_synthetic_amplicon_coordinates(self):
        template = ("A" * 10) + "CCGTAGCTAGCTAGCGTACCG" + ("A" * 40) + "CGTACGTACGTAGGCTAACCCG" + ("A" * 30)
        # left binds at index 10..31, right target region 52..72
        left = template[10:31]
        right = reverse_complement(template[52:72])
        pcr = in_silico_pcr(template, left, right,
                            expected_product=(72 - 10), left_expected=10, right_expected=71)
        assert 10 in pcr["forward_positions"]
        assert 52 in pcr["reverse_positions"]
        assert pcr["specific"]
        assert pcr["primer3_consistent"]
        assert pcr["matches_product_size"] is True

    def test_primers_bind_reference_at_expected_spots(self):
        # Reference primers spanning the entire TP53 CDS (NM_000546.6):
        #   forward  = 5'-ATGGAGGAGCCGCAGTCAGA-3'   -> CDS start (index 0)
        #   reverse  = 5'-TCAGTCTGAGTCAGGCCCTT-3'   -> reverse complement of
        #              the CDS end (anneals at index 1162, 20 bases 1162..1181)
        fwd = "ATGGAGGAGCCGCAGTCAGA"
        rev = "TCAGTCTGAGTCAGGCCCTT"
        assert find_binding_sites(TP53_CDS, fwd) == [0], "forward primer must bind TP53 CDS start"
        assert find_binding_sites(TP53_CDS, reverse_complement(rev)) == [1162], (
            "reverse primer must bind TP53 CDS end"
        )

    def test_nonbinding_primer_flagged(self):
        pcr = in_silico_pcr(TP53_CDS, "TTTTTTTTTTTTTTTTTT", "AAAAAAAAAAAAAAAAAAAA",
                            expected_product=200, left_expected=0, right_expected=199)
        assert pcr["specific"] is False
        assert pcr["matches_product_size"] is False
        assert pcr["note"]


# ============================================================================
# 4. End-to-end Primer3 design on TP53 CDS — verify every returned pair
# ============================================================================

@pytest.fixture(scope="module")
def primer_client():
    app = FastAPI(title="Primer Tests")
    from app.routers import primers
    app.include_router(primers.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_design_primers_on_tp53_and_verify_pairs(primer_client):
    resp = primer_client.post("/api/primers/design", json={
        "sequence": TP53_CDS,
        "product_size_min": 100,
        "product_size_max": 500,
        "opt_tm": 60,
        "num_return": 5,
    })
    assert resp.status_code == 200, resp.text
    pairs = resp.json()
    assert len(pairs) >= 1

    template = TP53_CDS
    for p in pairs:
        # Primer3 coordinate invariants
        assert p["product_size"] == p["right_pos"] - p["left_pos"] + 1, (
            f"pair {p['pair_index']}: product size inconsistent with positions"
        )
        # Primers are valid DNA of Primer3-default length
        assert 18 <= p["left_len"] <= 25 and 18 <= p["right_len"] <= 25
        assert set(p["left_seq"]) <= set("ATGCN") and set(p["right_seq"]) <= set("ATGCN")

        # Forward primer occurs at the reported position
        assert template[p["left_pos"]:p["left_pos"] + p["left_len"]] == p["left_seq"], (
            f"pair {p['pair_index']}: forward primer not at reported position"
        )
        # Reverse primer is the reverse complement of the template region
        r_start = p["right_pos"] - p["right_len"] + 1
        assert template[r_start:p["right_pos"] + 1] == reverse_complement(p["right_seq"]), (
            f"pair {p['pair_index']}: reverse primer mismatch in template"
        )

        # In-silico PCR reproduces Primer3's product size & coordinates
        pcr = in_silico_pcr(template, p["left_seq"], p["right_seq"],
                            expected_product=p["product_size"],
                            left_expected=p["left_pos"], right_expected=p["right_pos"])
        assert pcr["primer3_consistent"], f"pair {p['pair_index']}: in-silico PCR disagrees with Primer3"
        assert pcr["matches_product_size"] is True, f"pair {p['pair_index']}: amplicon length mismatch"


def test_analyze_endpoint_reference_pair(primer_client):
    # Known-good pair spanning the full TP53 CDS (NM_000546.6):
    # forward binds CDS index 0, reverse primer 3' end maps to index 1181
    # (its target region is 1162..1181), amplicon = 1182 bp.
    left, right = "ATGGAGGAGCCGCAGTCAGA", "TCAGTCTGAGTCAGGCCCTT"
    resp = primer_client.post("/api/primers/analyze", json={
        "left_seq": left,
        "right_seq": right,
        "template": TP53_CDS,
        "expected_product": 1182,
        "left_pos": 0,
        "right_pos": 1181,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["qc"]["left"]["gc"] > 40.0 and body["qc"]["left"]["gc"] < 70.0
    assert 45 <= body["qc"]["left"]["tm_50mM"] <= 70
    assert "hairpin" in body["qc"]["left"]
    assert "self_dimer" in body["qc"]["left"]
    assert "hetero_dimer" in body["qc"]
    assert body["pcr"]["primer3_consistent"] is True
    assert body["pcr"]["matches_product_size"] is True


def test_analyze_endpoint_rejects_protein(primer_client):
    resp = primer_client.post("/api/primers/analyze", json={
        "left_seq": "MKFLVLFLLGLVA",
        "right_seq": "ACDEFGHIKLMNP",
    })
    assert resp.status_code == 400
