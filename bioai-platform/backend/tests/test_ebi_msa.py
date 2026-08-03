"""
Tests for 3b multi-method MSA:

- EBI_TOOLS catalog covers all five methods with correct base URLs
- AlignRequest defaults to clustalo (backwards compatible)
- POST /api/alignment/run validates method before any network call
- run_alignment delegates to the shared run_ebi_msa and preserves response shape

All network calls are mocked; these run fully offline.
"""

import pytest
from fastapi import HTTPException

from app.tools.ebi_msa import EBI_TOOLS, run_ebi_msa
from app.routers import alignment as alignment_router
from app.routers.alignment import AlignRequest, run_alignment


class TestEbiToolsCatalog:
    def test_five_methods_present(self):
        assert set(EBI_TOOLS) == {"clustalo", "muscle", "kalign", "mafft", "tcoffee"}

    def test_base_urls_match_tool_name(self):
        for name, url in EBI_TOOLS.items():
            assert url.endswith(f"/rest/{name}")
            assert url.startswith("https://www.ebi.ac.uk/Tools/services/rest/")


class TestAlignRequestModel:
    def test_default_method_clustalo(self):
        req = AlignRequest(sequence=">a\nMEEPQSDPSV")
        assert req.method == "clustalo"

    def test_explicit_method_accepted(self):
        req = AlignRequest(sequence=">a\nMEEPQSDPSV", method="mafft")
        assert req.method == "mafft"


class TestRunAlignment:
    @pytest.mark.asyncio
    async def test_invalid_method_rejected_before_network(self):
        req = AlignRequest(sequence=">a\nMEEPQSDPSV", method="clustalw")
        with pytest.raises(HTTPException) as exc:
            await run_alignment(req)
        assert exc.value.status_code == 400
        assert "method must be one of" in exc.value.detail

    @pytest.mark.asyncio
    async def test_success_delegates_to_shared_runner(self, monkeypatch):
        canned = {
            "job_id": "job-1",
            "aln_fasta": ">a\nMEEPQSDPSV\n",
            "phylotree": "(a:0.0,b:0.1);",
            "method": "muscle",
        }

        async def fake_run_ebi_msa(**kwargs):
            assert kwargs["base_url"] == EBI_TOOLS["muscle"]
            return canned

        monkeypatch.setattr(alignment_router, "run_ebi_msa", fake_run_ebi_msa)
        req = AlignRequest(sequence=">a\nMEEPQSDPSV\n>b\nMEEPQSDPSA", method="muscle")
        result = await run_alignment(req)
        assert result["job_id"] == "job-1"
        assert result["aln_fasta"] == canned["aln_fasta"]
        assert result["phylotree"] == canned["phylotree"]
        assert result["stype"] == "protein"
        assert result["method"] == "muscle"

    @pytest.mark.asyncio
    async def test_runner_failure_maps_to_502(self, monkeypatch):
        async def fake_run_ebi_msa(**kwargs):
            raise ValueError("EBI submission failed (HTTP 500): boom")

        monkeypatch.setattr(alignment_router, "run_ebi_msa", fake_run_ebi_msa)
        req = AlignRequest(sequence=">a\nMEEPQSDPSV")
        with pytest.raises(HTTPException) as exc:
            await run_alignment(req)
        assert exc.value.status_code == 502
        assert "boom" in exc.value.detail
