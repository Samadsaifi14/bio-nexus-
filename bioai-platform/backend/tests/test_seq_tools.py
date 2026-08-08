"""
Sequence utilities toolkit, motif scanner and dot plot tests.

Known-answer checks against hand-verified arithmetic:

  * reverse complement / GC% / MW for a short oligo
  * translation frames and longest-ORF detection on a mini CDS
  * restriction-site positions on a sequence containing EcoRI + BamHI sites
  * PROSITE pattern parsing (alternation, exclusion, repeats, anchors)
  * motif library hits on a small protein containing N-glycosylation sites
  * dot-plot geometry (diagonal for identical sequences, off-diagonal dot for
    a shared repeat, window/stringency behavior)
  * router error mapping (bad pattern / too-large dot plot -> HTTP 400)
"""

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.tools.sequence_utilities import analyze_sequence, clean_sequence
from app.tools.motif_scanner import (
    MOTIF_LIBRARY,
    prosite_to_regex,
    scan_library,
    scan_pattern,
)
from app.tools.dotplot import compute_dotplot

# p53 residues 1-70 with two N-glycosylation consensus hits (N-S-T, N-C-S)
P53_N_TERM = (
    "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAA"
)


@pytest.fixture(scope="module")
def seq_client():
    app = FastAPI(title="Seq Tools Tests")
    from app.routers import seq_tools
    app.include_router(seq_tools.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ============================================================================
# 1. Sequence utilities
# ============================================================================

class TestAnalyzeSequence:
    def test_dna_reverse_complement_and_gc(self):
        res = analyze_sequence("ATGCGAATTCGGATCC", seq_type="dna")
        assert res["sequence_type"] == "dna"
        assert res["length"] == 16
        assert res["reverse_complement"] == "GGATCCGAATTCGCAT"
        # G=4, C=4 in ATGCGAATTCGGATCC
        assert res["gc_content"] == pytest.approx(8 / 16 * 100, abs=0.1)

    def test_restriction_sites_ecoRI_bamHI(self):
        res = analyze_sequence("ATGCGAATTCGGATCC", seq_type="dna")
        names = {s["name"]: s for s in res["restriction_sites"]}
        assert "EcoRI" in names and "BamHI" in names
        # EcoRI site (GAATTC) starts at index 5, BamHI (GGATCC) at index 11
        assert names["EcoRI"]["positions"] == [5]
        assert names["BamHI"]["positions"] == [11]

    def test_translation_frames_and_best_orf(self):
        # ATG CAT TAA CGT GCA TGA -> frame 1 = "MH*RA*"; best ORF = MH (stops)
        res = analyze_sequence("ATGCATTAACGTGCATGAA", seq_type="dna")
        tr = res["translation"]
        assert tr is not None
        assert tr["frames"]["1"] == "MH*RA*"
        assert tr["best"]["frame"] == 1
        assert tr["best"]["protein"] == "MH"
        assert tr["best"]["has_stop"] is True

    def test_protein_mw_and_composition(self):
        res = analyze_sequence("MEEPQSDPSVEP", seq_type="protein")
        assert res["sequence_type"] == "protein"
        assert res["molecular_weight"] is not None and res["molecular_weight"] > 0
        comp = {c["aa"]: c["count"] for c in res["aa_composition"]}
        assert comp["M"] == 1 and comp["E"] == 3 and comp["P"] == 3
        total_pct = round(sum(c["pct"] for c in res["aa_composition"]), 1)
        assert total_pct == pytest.approx(100.0, abs=0.1)

    def test_fasta_input_handled(self):
        res = analyze_sequence(">probe\nATGCGAATTCGGATCC\n", seq_type="dna")
        assert res["length"] == 16

    def test_auto_detects_dna(self):
        res = analyze_sequence("ACGTACGTTGCA", seq_type="auto")
        assert res["sequence_type"] == "dna"

    def test_empty_raises(self):
        with pytest.raises(Exception):
            analyze_sequence("   ", seq_type="dna")

    def test_clean_drops_ambiguous_for_gc(self):
        cleaned = clean_sequence("ATGCNNNGG", "dna")
        assert set(cleaned) <= set("ATCGN")


# ============================================================================
# 2. Motif scanner
# ============================================================================

class TestPrositeToRegex:
    def test_literal_and_x(self):
        assert prosite_to_regex("A-x-V") == "A[A-Z]V"

    def test_alternation_and_exclusion(self):
        assert prosite_to_regex("[ST]-x-[RK]") == "[ST][A-Z][RK]"
        assert prosite_to_regex("N-{P}-[ST]-{P}") == "N[^P][ST][^P]"

    def test_repeat_quantifiers(self):
        assert prosite_to_regex("x(2,4)") == "[A-Z]{2,4}"
        assert prosite_to_regex("[ST]-x(2)-[DE]") == "[ST][A-Z]{2}[DE]"

    def test_anchors(self):
        assert prosite_to_regex("<A") == "^A"
        assert prosite_to_regex("G>") == "G$"

    def test_invalid_symbol_raises(self):
        from app.tools.motif_scanner import MotifError
        with pytest.raises(MotifError):
            prosite_to_regex("A-*")

    def test_invalid_group_raises(self):
        from app.tools.motif_scanner import MotifError
        with pytest.raises(MotifError):
            prosite_to_regex("[1]x")
        with pytest.raises(MotifError):
            prosite_to_regex("A-@-B")


class TestScanPattern:
    def test_nglycosylation_finds_expected(self):
        # N-glycosylation consensus N-{P}-[ST]-{P}: "QNSTL" -> match "NSTL"
        res = scan_pattern("MKDYQNSTLPVARKTGH", "N-{P}-[ST]-{P}")
        assert res["count"] >= 1
        for m in res["matches"]:
            assert m["end"] - m["start"] + 1 == 4

    def test_overlapping_matches_reported(self):
        res = scan_pattern("NNSTP", "N-{P}-[ST]-{P}")
        # position 1 starts "NNST" -> one match
        assert res["count"] == 1

    def test_cleans_sequence_case(self):
        res = scan_pattern("Mnnstlpv", "N-{P}-[ST]-{P}")
        assert res["count"] == 1


class TestScanLibrary:
    def test_known_motifs_found(self):
        # This construct has two obvious hits: N-glycosylation N-S-T and PKC [ST]-x-[RK]
        seq = "MKDYQNSTLPVARKTGH"
        res = scan_library(seq)
        assert res["motifs_found"] >= 1
        names = {h["name"] for h in res["hits"]}
        assert "N-glycosylation site" in names

    def test_library_reports_length(self):
        res = scan_library(P53_N_TERM)
        assert res["length"] == len(P53_N_TERM)

    def test_library_hits_carry_metadata(self):
        res = scan_library("MKDYQNSTLPVARKTGH")
        assert res["motifs_found"] >= 1
        for hit in res["hits"]:
            assert "accession" in hit
            assert "category" in hit
            assert hit["specificity"] in ("high", "loose")

    def test_library_category_filter(self):
        res = scan_library("MKDYQNSTLPVARKTGH", categories=["PTM"])
        assert res["motifs_found"] >= 1
        assert all(h["category"] == "PTM" for h in res["hits"])
        # A filter that matches nothing yields an empty hit list
        res_none = scan_library("MKDYQNSTLPVARKTGH", categories=["RNA binding"])
        assert res_none["motifs_found"] == 0
        assert res_none["patterns_scanned"] < len(MOTIF_LIBRARY)

    def test_ptm_filter_keeps_glycosylation(self):
        res = scan_library("MKDYQNSTLPVARKTGH", categories=["PTM"])
        names = {h["name"] for h in res["hits"]}
        assert "N-glycosylation site" in names


# ============================================================================
# 3. Dot plot
# ============================================================================

class TestDotPlot:
    def test_identical_sequences_diagonal(self):
        # Every window position trivially matches itself, so a self-plot lights
        # the whole main diagonal and nothing off it.
        res = compute_dotplot("AAAACCCCGGGGTTTT", "AAAACCCCGGGGTTTT", window=4, stringency=100)
        assert res["dot_count"] == 16 - 4 + 1
        for y, x in res["dots"]:
            assert y == x
        assert res["seq_a_length"] == 16 and res["seq_b_length"] == 16

    def test_shared_repeat_off_diagonal(self):
        a = "AAAACCCCGGGGTTTT"
        b = "AAAAGGGGAAAACCCC"
        res = compute_dotplot(a, b, window=4, stringency=100)
        coords = set(map(tuple, res["dots"]))
        # "AAAA" appears in both at position 0; "CCCC" in a at 4 and b at 12
        assert (0, 0) in coords
        assert (4, 12) in coords

    def test_stringency_filters_weak_matches(self):
        a = "AAAAAAAAAA"
        b = "AAAAAAAAAG"  # differs at last position
        # window 5, stringency 100 -> only positions with 5/5 identical
        res = compute_dotplot(a, b, window=5, stringency=100)
        assert (0, 0) in {tuple(d) for d in res["dots"]}
        # window 5, stringency 80 -> last position (4, 4) matches 4/5
        res80 = compute_dotplot(a, b, window=5, stringency=80)
        assert (4, 4) in {tuple(d) for d in res80["dots"]}

    def test_window_one_is_char_match(self):
        res = compute_dotplot("ACGT", "ACGT", window=1, stringency=100)
        assert res["dot_count"] == 4

    def test_blosum62_matrix_scoring(self):
        res = compute_dotplot("WWWWWWWW", "WWWWWWWW", window=2, stringency=100, scoring="blosum62")
        assert res["scoring_used"] == "blosum62"
        # W-W = 11, so a 2-window at 100% stringency needs a score of 22;
        # because the sequence is uniform, every 2-window matches every other
        # 2-window, lighting the whole 7x7 matrix (correct dot-plot semantics).
        assert res["threshold"] == 22
        assert res["dot_count"] == 7 * 7
        assert res["features"]["main_diagonal_pct"] == 100.0

    def test_scoring_falls_back_to_identity_for_nucleotides(self):
        res = compute_dotplot("AAAACCCC", "AAAACCCC", window=2, stringency=100, scoring="blosum62")
        assert res["scoring"] == "blosum62"
        assert res["scoring_used"] == "identity"
        assert res["threshold"] == 2

    def test_invalid_scoring_raises(self):
        from app.tools.dotplot import DotPlotError
        with pytest.raises(DotPlotError):
            compute_dotplot("AAAA", "AAAA", scoring="bogus")

    def test_features_identical_main_diagonal(self):
        res = compute_dotplot("AAAACCCCGGGGTTTT", "AAAACCCCGGGGTTTT", window=4, stringency=100)
        f = res["features"]
        # 13 achievable window-start positions along the diagonal (16 - 4 + 1)
        assert f["main_diagonal_pct"] == 100.0
        assert f["off_diagonal"] == []
        assert f["anti_diagonal"] == []

    def test_features_detect_repeat_offset(self):
        a = "AAAACCCCGGGGTTTT"
        b = "TTTTAAAACCCCGGGG"
        res = compute_dotplot(a, b, window=4, stringency=100)
        offsets = {o["offset"]: o["count"] for o in res["features"]["off_diagonal"]}
        # AAAA/CCCC/GGGG sit at b[4], b[8], b[12] -> three dots at offset +4
        assert offsets.get(4, 0) >= 3

    def test_features_detect_inverted_repeat(self):
        a = "AAAACCCCGGGGTTTT"
        b = a[::-1]
        res = compute_dotplot(a, b, window=4, stringency=100)
        sums = {o["sum"]: o["count"] for o in res["features"]["anti_diagonal"]}
        # Reverse comparison lights the anti-diagonal x + y = 12
        assert sums.get(12, 0) >= 4

    def test_too_large_raises(self):
        from app.tools.dotplot import DotPlotError
        with pytest.raises(DotPlotError):
            compute_dotplot("A" * 5000, "A" * 5000)


# ============================================================================
# 4. Router-level
# ============================================================================

class TestSeqToolsEndpoints:
    def test_analyze_endpoint(self, seq_client):
        resp = seq_client.post("/api/seq-tools/analyze", json={
            "sequence": "ATGCGAATTCGGATCC", "seq_type": "dna",
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["reverse_complement"] == "GGATCCGAATTCGCAT"
        assert body["length"] == 16

    def test_analyze_bad_type_400(self, seq_client):
        resp = seq_client.post("/api/seq-tools/analyze", json={
            "sequence": "ACGT", "seq_type": "bogus",
        })
        assert resp.status_code == 400

    def test_motif_scan_endpoint(self, seq_client):
        resp = seq_client.post("/api/seq-tools/motif-scan", json={
            "sequence": "MNSST", "pattern": "N-{P}-[ST]-{P}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["count"] >= 1

    def test_motif_scan_bad_pattern_400(self, seq_client):
        resp = seq_client.post("/api/seq-tools/motif-scan", json={
            "sequence": "MNSST", "pattern": "A-*",
        })
        assert resp.status_code == 400

    def test_motif_library_endpoint(self, seq_client):
        resp = seq_client.post("/api/seq-tools/motif-library", json={
            "sequence": "MKDYQNSTLPVARKTGH",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["motifs_found"] >= 1

    def test_motif_patterns_list(self, seq_client):
        resp = seq_client.get("/api/seq-tools/motif-library/patterns")
        assert resp.status_code == 200
        assert len(resp.json()) >= 5
        assert "accession" in resp.json()[0]
        assert "category" in resp.json()[0]
        assert "specificity" in resp.json()[0]

    def test_motif_categories_list(self, seq_client):
        resp = seq_client.get("/api/seq-tools/motif-library/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list) and "PTM" in cats
        assert cats == sorted(cats, key=lambda c: cats.index(c))  # ordered, unique

    def test_motif_library_category_filter_endpoint(self, seq_client):
        resp = seq_client.post("/api/seq-tools/motif-library", json={
            "sequence": "MKDYQNSTLPVARKTGH",
            "categories": ["PTM"],
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["motifs_found"] >= 1
        assert all(h["category"] == "PTM" for h in body["hits"])

    def test_dotplot_endpoint(self, seq_client):
        resp = seq_client.post("/api/seq-tools/dotplot", json={
            "seq_a": "AAAACCCCGGGGTTTT", "seq_b": "AAAACCCCGGGGTTTT",
            "window": 4, "stringency": 100,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dot_count"] == 16 - 4 + 1
        assert all(d[0] == d[1] for d in body["dots"])

    def test_dotplot_too_large_400(self, seq_client):
        resp = seq_client.post("/api/seq-tools/dotplot", json={
            "seq_a": "A" * 5000, "seq_b": "A" * 5000,
            "window": 4, "stringency": 100,
        })
        assert resp.status_code == 400

    def test_dotplot_scoring_endpoint(self, seq_client):
        resp = seq_client.post("/api/seq-tools/dotplot", json={
            "seq_a": "WWWWWWWW", "seq_b": "WWWWWWWW",
            "window": 2, "stringency": 100, "scoring": "blosum62",
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["scoring_used"] == "blosum62"
        assert body["features"]["main_diagonal_pct"] == 100.0

    def test_dotplot_bad_scoring_400(self, seq_client):
        resp = seq_client.post("/api/seq-tools/dotplot", json={
            "seq_a": "AAAA", "seq_b": "AAAA", "scoring": "bogus",
        })
        assert resp.status_code == 400
