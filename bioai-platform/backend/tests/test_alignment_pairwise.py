"""
Tests for 3a pairwise alignment:

- pairwise_align() correctness (known-answer, global vs local, identical, no-overlap)
- fetch_sequence_by_accession() NCBI-first / UniProt-fallback / both-fail
- POST /api/alignment/pairwise router: success, query-by-accession, fetch-failure -> 400

All network calls are mocked; these run fully offline.
"""

import pytest
from fastapi import HTTPException

from app.tools.pairwise_alignment import PairwiseAlignError, pairwise_align
from app.tools import sequence_fetch as sf
from app.routers import alignment as alignment_router
from app.routers.alignment import PairwiseAlignRequest, run_pairwise


class TestPairwiseAlign:
    def test_identical_sequences_global(self):
        res = pairwise_align("ACDEFGHIK", "ACDEFGHIK")
        assert res["mode"] == "global"
        assert res["pct_identity"] == 100.0
        assert res["identity"] == 9
        assert res["alignment_length"] == 9
        assert res["gaps_total"] == 0
        assert res["gap_positions"] == []
        assert res["query_start"] == 1 and res["query_end"] == 9
        assert res["hit_start"] == 1 and res["hit_end"] == 9
        assert res["score"] > 0

    def test_known_answer_trailing_overhang(self):
        # Query MKTQ vs subject MKTQQQ (BLOSUM62, open=-10, extend=-1).
        # Optimal global alignments score 5+5+5+5 -10 -1 = 9 with identity 4/6.
        # The optimal alignment is degenerate (a single 2-residue gap run in the
        # query either after residue 3 or 4), so assert the invariants only.
        res = pairwise_align("MKTQ", "MKTQQQ")
        assert res["score"] == 9.0
        assert res["identity"] == 4
        assert res["pct_identity"] == 66.7
        assert res["alignment_length"] == 6
        assert len(res["gap_positions"]) == 1
        assert res["gap_positions"][0]["seq"] == "query"
        assert res["gap_positions"][0]["length"] == 2
        assert res["gaps_total"] == 2
        assert res["query_start"] == 1 and res["query_end"] == 4
        assert res["hit_start"] == 1 and res["hit_end"] == 6

    def test_local_vs_global_divergence(self):
        query = "ACGTACGTACGT"
        subject = "ACGTACGT"
        g = pairwise_align(query, subject, mode="global")
        l = pairwise_align(query, subject, mode="local")
        # Global must align the full query, so the trailing overhang counts:
        assert g["pct_identity"] < 90
        assert g["alignment_length"] == 12
        # Local re-finds the perfect match:
        assert l["pct_identity"] == 100.0
        assert l["alignment_length"] == 8

    def test_no_overlap_local_returns_valid_result(self):
        res = pairwise_align("AAAA", "CCCC", mode="local")
        assert res["pct_identity"] == 0.0
        assert res["identity"] == 0
        assert res["alignment_length"] == 0
        assert res["aligned_query"] == ""
        assert res["aligned_hit"] == ""
        assert res["query_start"] == 0 and res["hit_start"] == 0

    def test_pam250_matrix_accepted(self):
        res = pairwise_align("ACDEFGHIK", "ACDEFGHIK", matrix="pam250")
        assert res["pct_identity"] == 100.0
        assert res["matrix"] == "pam250"

    def test_invalid_mode_raises(self):
        with pytest.raises(PairwiseAlignError):
            pairwise_align("ACGT", "ACGT", mode="semiglobal")

    def test_invalid_matrix_raises(self):
        with pytest.raises(PairwiseAlignError):
            pairwise_align("ACGT", "ACGT", matrix="gonnet")

    def test_empty_sequence_raises(self):
        with pytest.raises(PairwiseAlignError):
            pairwise_align("", "ACGT")


class TestFetchSequenceByAccession:
    async def test_ncbi_first(self, monkeypatch):
        async def fake_ncbi(accession):
            return {"accession": accession, "sequence": "ACGT", "length": 4}
        async def fake_uni(accession):
            raise AssertionError("UniProt fallback should not be called on NCBI success")
        monkeypatch.setattr(sf._ncbi, "fetch_by_accession", fake_ncbi)
        monkeypatch.setattr(sf._uniprot, "fetch_uniprot_fasta", fake_uni)
        res = await sf.fetch_sequence_by_accession("NP_000000.1")
        assert res["source"] == "ncbi"
        assert res["sequence"] == "ACGT"

    async def test_uniprot_fallback(self, monkeypatch):
        async def fake_ncbi(accession):
            return {"error": "not found"}
        async def fake_uni(accession):
            return {"accession": accession, "sequence": "MKLV", "length": 4}
        monkeypatch.setattr(sf._ncbi, "fetch_by_accession", fake_ncbi)
        monkeypatch.setattr(sf._uniprot, "fetch_uniprot_fasta", fake_uni)
        res = await sf.fetch_sequence_by_accession("P04637")
        assert res["source"] == "uniprot"
        assert res["sequence"] == "MKLV"

    async def test_both_sources_fail(self, monkeypatch):
        async def fake_ncbi(accession):
            return {"error": "not found"}
        async def fake_uni(accession):
            return {"error": "not found"}
        monkeypatch.setattr(sf._ncbi, "fetch_by_accession", fake_ncbi)
        monkeypatch.setattr(sf._uniprot, "fetch_uniprot_fasta", fake_uni)
        res = await sf.fetch_sequence_by_accession("DEAD0001")
        assert "error" in res

    async def test_forced_source(self, monkeypatch):
        called = []
        async def fake_uni(accession):
            called.append(accession)
            return {"accession": accession, "sequence": "MKLV", "length": 4}
        monkeypatch.setattr(sf._uniprot, "fetch_uniprot_fasta", fake_uni)
        res = await sf.fetch_sequence_by_accession("p04637", source="uniprot")
        assert res["source"] == "uniprot"
        assert called == ["P04637"]  # sanitized to uppercase

    async def test_invalid_source(self, monkeypatch):
        res = await sf.fetch_sequence_by_accession("P04637", source="ensembl")
        assert "error" in res


class TestPairwiseEndpoint:
    async def test_success_with_query_sequence(self, monkeypatch):
        async def fake_fetch(accession, source="auto"):
            return {"accession": accession, "source": "ncbi", "sequence": "MKTQQQ"}
        monkeypatch.setattr(alignment_router, "fetch_sequence_by_accession", fake_fetch)
        req = PairwiseAlignRequest(hit_accession="XP_123", query_sequence="MKTQ")
        res = await run_pairwise(req)
        assert res["hit_source"] == "ncbi"
        assert res["pct_identity"] == 66.7
        assert res["mode"] == "global"

    async def test_query_by_accession(self, monkeypatch):
        calls = {}
        async def fake_fetch(accession, source="auto"):
            calls[accession] = source
            return {"accession": accession, "source": "uniprot", "sequence": "ACGTACGT"}
        monkeypatch.setattr(alignment_router, "fetch_sequence_by_accession", fake_fetch)
        req = PairwiseAlignRequest(hit_accession="H1", query_accession="Q1")
        res = await run_pairwise(req)
        assert calls == {"Q1": "auto", "H1": "auto"}
        assert res["pct_identity"] == 100.0

    async def test_fetch_failure_returns_400(self, monkeypatch):
        async def fake_fetch(accession, source="auto"):
            return {"error": "Could not retrieve sequence for accession 'X'"}
        monkeypatch.setattr(alignment_router, "fetch_sequence_by_accession", fake_fetch)
        req = PairwiseAlignRequest(hit_accession="DEAD0001", query_sequence="ACGT")
        with pytest.raises(HTTPException) as excinfo:
            await run_pairwise(req)
        assert excinfo.value.status_code == 400
        assert "DEAD0001" in excinfo.value.detail

    async def test_invalid_mode_returns_400_before_fetch(self, monkeypatch):
        async def fake_fetch(accession, source="auto"):
            raise AssertionError("fetch should not be called for invalid mode")
        monkeypatch.setattr(alignment_router, "fetch_sequence_by_accession", fake_fetch)
        req = PairwiseAlignRequest(hit_accession="H1", query_sequence="ACGT", mode="semiglobal")
        with pytest.raises(HTTPException) as excinfo:
            await run_pairwise(req)
        assert excinfo.value.status_code == 400

    async def test_missing_query_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            alignment_router,
            "fetch_sequence_by_accession",
            lambda accession, source="auto": None,
        )
        req = PairwiseAlignRequest(hit_accession="H1")
        with pytest.raises(HTTPException) as excinfo:
            await run_pairwise(req)
        assert excinfo.value.status_code == 400
