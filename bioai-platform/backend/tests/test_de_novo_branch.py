"""Tests for the tier-6 de novo branch (techspec.md §1)."""

import pytest

from app.routers import pipeline_v2 as pv
from app.services import de_novo


# ── ESMFold structure card ──────────────────────────────────────────────────

_PDB_SNIPPET = "\n".join([
    "ATOM      1  CA  ALA A   1      11.104   6.134  -6.504  1.00 92.11           C",
    "ATOM      2  CA  GLY A   2      11.986   6.953  -5.601  1.00 87.42           C",
    "ATOM      3  CA  SER A   3      12.594   8.301  -6.021  1.00 43.05           C",
    "END",
])


def test_mean_plddt_from_pdb():
    assert de_novo._mean_plddt_from_pdb(_PDB_SNIPPET) == round((92.11 + 87.42 + 43.05) / 3, 1)


@pytest.mark.asyncio
async def test_esmfold_structure_shape(monkeypatch):
    async def fake_predict(seq):
        return _PDB_SNIPPET

    monkeypatch.setattr("app.tools.structure_prep.esmfold_predict", fake_predict)
    result = await de_novo.esmfold_structure("ACDEFGHIKLM")
    assert result["structure_available"] is True
    assert result["source"] == "esmfold"
    assert result["pdb_text"] == _PDB_SNIPPET
    assert result["mean_plddt"] == 74.2
    assert result["uniprot_accession"] is None


@pytest.mark.asyncio
async def test_esmfold_structure_failure_is_explicit(monkeypatch):
    async def fake_predict(seq):
        return None

    monkeypatch.setattr("app.tools.structure_prep.esmfold_predict", fake_predict)
    result = await de_novo.esmfold_structure("ACDEFGHIKLM")
    assert result["structure_available"] is False
    assert "_note" in result


# ── InterProScan normalization ───────────────────────────────────────────────

_IPRSCAN_JSON = {
    "results": [{
        "length": 12,
        "matches": [{
            "signature": {
                "accession": "PF00096",
                "name": "zf-CCHH",
                "signatureLibraryRelease": {"library": "PFAM"},
                "entry": {
                    "accession": "IPR007087",
                    "name": "Zinc finger",
                    "sourceDatabase": "interpro",
                },
            },
            "locations": [{"start": 2, "end": 9}],
        }],
    }],
}


class _FakeResp:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeIprscanClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        return _FakeResp(200, text="iprscan-job-1\n")

    async def get(self, url, **kw):
        if "/status/" in url:
            return _FakeResp(200, text="FINISHED\n")
        if url.endswith("/json"):
            return _FakeResp(200, json_data=_IPRSCAN_JSON)
        return _FakeResp(404)


@pytest.mark.asyncio
async def test_interpro_sequence_search_normalizes(monkeypatch):
    monkeypatch.setattr(de_novo.httpx, "AsyncClient", lambda *a, **k: _FakeIprscanClient())
    monkeypatch.setattr(de_novo, "POLL_INTERVAL_S", 0)
    result = await de_novo.interpro_sequence_search("ACDEFGHIKLMN")
    assert result["source"] == "interproscan5"
    assert result["sequence_length"] == 12
    d = result["domains"][0]
    assert d["accession"] == "IPR007087"  # InterPro entry preferred over PFAM sig
    assert d["start"] == 2 and d["end"] == 9


# ── Composition + function hints (local, real calls) ────────────────────────


def test_composition_stats_runs_accession_free():
    result = de_novo.composition_stats("ACDEFGHIKLMNPQRSTVWYACDEFGHIKL")
    assert result["sequence_type"] == "protein"
    assert result["_note"]


def test_function_hints_are_labeled_heuristic():
    result = de_novo.function_hints("ACDEFGHIKLMNPQRSTVWYMLLLLLLLLVVAA")
    assert result["go_terms"]
    assert "Heuristic" in result["_note"]
    assert result["source"] == "composition_heuristic"


# ── Pipeline-level: zero-hit protein completes instead of failing ───────────


@pytest.mark.asyncio
async def test_zero_hit_protein_run_completes_denovo(monkeypatch):
    """Acceptance §1.4: synthetic sequence produces a completed run."""
    job_id = "denovo-test-1"

    async def fake_blast(*a, **k):
        return {"error": "No hits", "count": 0, "hits": [], "top_hit": None}

    async def fake_ipro(sequence, email=""):
        return {"domains": [], "sequence_length": len(sequence), "source": "interproscan5"}

    async def fake_fold(sequence):
        return {"structure_available": True, "source": "esmfold", "pdb_text": _PDB_SNIPPET,
                "mean_plddt": 74.2, "pdb_url": None, "cif_url": None, "confidence": 0.74,
                "uniprot_accession": None, "_note": "x"}

    persisted = {}
    monkeypatch.setattr(pv, "_run_blast", fake_blast)
    monkeypatch.setattr(pv, "_persist_v2_final", lambda jid, status, ctx, error=None: persisted.update(status=status))
    monkeypatch.setattr("app.services.de_novo.interpro_sequence_search", fake_ipro)
    monkeypatch.setattr("app.services.de_novo.esmfold_structure", fake_fold)

    steps = [s for s in pv.STEP_ORDER if s != "interpret"]
    pv._jobs[job_id] = {
        "job_id": job_id, "status": "running",
        "steps": {s: {"status": "pending", "progress": 0, "data": None, "error": None} for s in pv.STEP_ORDER},
    }
    await pv._execute(job_id, "QWERTYIPASDFGHKLCVMNEQRTPSTEPS", steps)

    job = pv._jobs.pop(job_id)
    assert job["status"] == "complete"
    assert persisted["status"] == "complete"

    # Confidence threaded through the query block
    assert job["context"]["query"]["confidence"] == "de_novo"

    step_status = {name: info["status"] for name, info in job["steps"].items()}
    assert step_status["blast"] == "complete"          # ran, just found nothing
    assert step_status["uniprot"] == "complete"        # composition/hints bundle
    assert step_status["domains"] == "complete"
    assert step_status["alphafold"] == "complete"

    # Annotation-database features explicitly unavailable, never silently empty
    for name in ("msa", "phylo", "pathway_enrichment"):
        assert step_status[name] == "failed"
        assert "no identified homolog" in job["steps"][name]["error"]

    bundle = job["steps"]["uniprot"]["data"]
    assert bundle["_de_novo"] is True
    assert "composition" in bundle and "function_hints" in bundle


@pytest.mark.asyncio
async def test_resolved_via_sequence_blast_gets_homolog_confidence(monkeypatch):
    """Tier-4 resolution marks results homolog, distinct from tier-1 identity."""
    job_id = "homolog-test-1"

    async def fake_blast(*a, **k):
        return {"count": 1, "hits": [{"accession": "XP_123456", "description": "some protein"}],
                "top_hit": {"accession": "XP_123456", "description": "some protein"}}

    async def fake_uniprot(candidate, query_sequence=None, try_sequence=True):
        return {
            "accession": "P04637", "resolved_uniprot": True, "confidence": "homolog",
            "gene_names": [], "functions": [], "keywords": [],
            "subcellular_locations": [], "pdb_ids": [], "go_terms": [],
            "sequence": "", "sequence_length": 0, "features": [],
            "resolution": {"uniprot_accession": "P04637", "method": "sequence",
                           "original_accession": "XP_123456"},
        }

    async def fake_domains(sequence, accession, resolved):
        return {"uniprot_accession": accession, "sequence_length": 100, "domains": []}

    async def fake_alphafold(context, sequence, accession, resolved):
        return {"structure_available": True, "pdb_url": "https://files.rcsb.org/x.pdb"}

    async def fake_msa(*a, **k):
        return {"error": "skip", "aln_fasta": None, "phylotree": None}

    async def fake_pathway(context):
        return {"pathways": []}

    monkeypatch.setattr(pv, "_run_blast", fake_blast)
    monkeypatch.setattr(pv, "_run_uniprot", fake_uniprot)
    monkeypatch.setattr(pv, "_run_msa", fake_msa)
    monkeypatch.setattr(pv, "_run_pathway_enrichment", fake_pathway)
    monkeypatch.setattr(pv, "_run_domains_or_denovo", fake_domains)
    monkeypatch.setattr(pv, "_run_alphafold_or_esmfold", fake_alphafold)

    steps = [s for s in pv.STEP_ORDER if s != "interpret"]
    pv._jobs[job_id] = {
        "job_id": job_id, "status": "running",
        "steps": {s: {"status": "pending", "progress": 0, "data": None, "error": None} for s in pv.STEP_ORDER},
    }
    await pv._execute(job_id, "MEEPQSDPSVEPPLSQETFSDLWKLLPENNV", steps)

    job = pv._jobs.pop(job_id)
    assert job["status"] == "complete"
    assert job["context"]["query"]["confidence"] == "homolog"
