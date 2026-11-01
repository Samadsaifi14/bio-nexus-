"""Background-job contracts for MSA and phylogenetics.

Both routes previously failed in production for reasons that unit tests did not
cover: the MSA job runner referenced a function that was never imported, and the
phylogeny router discarded the EMBL-EBI error body and had no aligned-input
fallback. These tests pin the shared execution path and the provider provenance.
"""

from __future__ import annotations

import pytest

from app.routers import alignment as alignment_router
from app.routers import phylo as phylo_router
from app.tools import msa_fallback

FASTA = ">a\nACDEFGHIKLMNPQRSTVWY\n>b\nACDEFGHIKLMNPQRSTVWY\n"
ALIGNED = ">a\nACDEFGHIKLMNPQRSTVWY\n>b\nACDEFGHIKLMNPQRSTVWY\n"


@pytest.fixture(autouse=True)
def _no_side_effect_writes(monkeypatch):
    """Keep the registry/mirror off the network for these unit tests."""
    for module in (alignment_router, phylo_router):
        monkeypatch.setattr(module.job_state, "mirror", lambda *a, **k: None)
        monkeypatch.setattr(module.job_registry, "propagate_patch", lambda *a, **k: None)
        monkeypatch.setattr(module.job_registry, "finish", lambda *a, **k: None)
        monkeypatch.setattr(module.job_registry, "start", lambda *a, **k: "registered")
        monkeypatch.setattr(module.job_registry, "record_completed", lambda *a, **k: None)
    yield
    alignment_router._jobs.clear()
    phylo_router._jobs.clear()


@pytest.mark.asyncio
async def test_msa_job_completes_with_provider_provenance(monkeypatch):
    async def fake_best_effort(**_kwargs):
        return {
            "job_id": "ebi-123",
            "aln_fasta": ALIGNED,
            "phylotree": "(a:1,b:1);",
            "method": "clustalo",
            "provider": "EMBL-EBI Job Dispatcher",
            "provider_fallback": False,
            "validation": {"sequence_count": 2},
        }

    monkeypatch.setattr(alignment_router, "run_ebi_msa_best_effort", fake_best_effort)

    req = alignment_router.AlignRequest(sequence=FASTA, stype="protein", method="clustalo")
    await alignment_router._run_msa_job("msa-job-1", req)

    job = alignment_router._jobs["msa-job-1"]
    assert job["status"] == "complete"
    assert job["aln_fasta"] == ALIGNED
    assert job["method"] == "clustalo"
    assert job["ebi_job_id"] == "ebi-123"
    # The EBI id is stored separately; it must not replace the local job id.
    assert "job_id" not in job


@pytest.mark.asyncio
async def test_msa_job_uses_labelled_local_fallback(monkeypatch):
    async def blocked(**_kwargs):
        raise RuntimeError("HTTP 400: temporarily blocked from submitting jobs")

    monkeypatch.setattr(alignment_router, "run_ebi_msa_best_effort", blocked)
    monkeypatch.setattr(
        msa_fallback, "progressive_msa", lambda records, stype: (ALIGNED, "(a:1,b:1);")
    )

    req = alignment_router.AlignRequest(sequence=FASTA, stype="protein", method="clustalo")
    await alignment_router._run_msa_job("msa-job-2", req)

    job = alignment_router._jobs["msa-job-2"]
    assert job["status"] == "complete"
    assert job["method"] == "in-process fallback"
    assert job["provider"] == "BioNexus local fallback"
    assert job["provider_fallback"] is True
    assert "temporarily blocked" in job["provider_error"]


@pytest.mark.asyncio
async def test_msa_job_rejects_invalid_fasta_before_provider(monkeypatch):
    called = False

    async def should_not_run(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be called for invalid input")

    monkeypatch.setattr(alignment_router, "run_ebi_msa_best_effort", should_not_run)

    req = alignment_router.AlignRequest(sequence=">a\n***\n>b\nAAA\n", stype="protein")
    await alignment_router._run_msa_job("msa-job-3", req)

    job = alignment_router._jobs["msa-job-3"]
    assert job["status"] == "failed"
    assert "invalid" in job["error"].lower()
    assert called is False


@pytest.mark.asyncio
async def test_ebi_submit_surfaces_provider_error_body(monkeypatch):
    class FakeResponse:
        status_code = 400
        text = "<error><description>temporarily blocked from submitting jobs</description></error>"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(phylo_router.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    with pytest.raises(RuntimeError) as exc:
        await phylo_router._ebi_submit("https://www.ebi.ac.uk/Tools/services/rest/clustalo", {})

    assert "400" in str(exc.value)
    assert "temporarily blocked" in str(exc.value)


@pytest.mark.asyncio
async def test_phylo_falls_back_to_local_alignment_with_provenance(monkeypatch):
    async def blocked(_url, _data):
        raise RuntimeError("HTTP 400: temporarily blocked from submitting jobs")

    monkeypatch.setattr(phylo_router, "_ebi_submit", blocked)
    monkeypatch.setattr(
        msa_fallback, "progressive_msa", lambda records, stype: (ALIGNED, "(a:1,b:1);")
    )
    phylo_router._jobs["phylo-1"] = {"status": "running"}

    result = await phylo_router._run_clustalo(
        "phylo-1",
        [{"id": "a", "sequence": "ACDEFGHIKLMNPQRSTVWY"},
         {"id": "b", "sequence": "ACDEFGHIKLMNPQRSTVWY"}],
        "protein",
    )

    assert result is not None
    aln_fasta, guide_tree = result
    assert aln_fasta == ALIGNED
    assert guide_tree == "(a:1,b:1);"

    job = phylo_router._jobs["phylo-1"]
    assert job["msa_provider"] == "BioNexus local fallback"
    assert "fallback" in job["msa_engine"].lower()
    assert "temporarily blocked" in job["msa_provider_error"]
    # A local fallback guide tree is UPGMA, never labelled as Clustal Omega.
    assert "UPGMA" in job["msa_guide_tree"]
    assert job["phase"] == "msa_done"


@pytest.mark.asyncio
async def test_phylo_fails_clearly_when_provider_and_fallback_fail(monkeypatch):
    async def blocked(_url, _data):
        raise RuntimeError("HTTP 400: temporarily blocked from submitting jobs")

    def broken_fallback(_records, _stype):
        raise ValueError("alignment cannot be produced")

    monkeypatch.setattr(phylo_router, "_ebi_submit", blocked)
    monkeypatch.setattr(msa_fallback, "progressive_msa", broken_fallback)
    phylo_router._jobs["phylo-2"] = {"status": "running"}

    result = await phylo_router._run_clustalo(
        "phylo-2", [{"id": "a", "sequence": "ACDE"}, {"id": "b", "sequence": "ACDE"}], "protein"
    )

    assert result is None
    job = phylo_router._jobs["phylo-2"]
    assert job["phase"] == "error"
    assert "temporarily blocked" in job["error"]
    assert "fallback also failed" in job["error"]
