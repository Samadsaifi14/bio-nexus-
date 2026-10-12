"""Offline audit checks for UniProt search-name and CDS provenance boundaries."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers import uniprot as router
from app.routers.uniprot import UniprotCDSRequest, UniprotSearchRequest


class _Resp:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class _Client:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_search_uses_submission_name_when_recommended_name_missing(monkeypatch):
    payload = {
        "results": [{
            "primaryAccession": "A0A1111111",
            "entryType": "UniProtKB unreviewed (TrEMBL)",
            "proteinDescription": {
                "submissionNames": [{"fullName": {"value": "Submitted enzyme name"}}]
            },
            "genes": [],
            "organism": {"scientificName": "Test organism"},
            "sequence": {"length": 123},
        }]
    }
    monkeypatch.setattr(router.httpx, "AsyncClient", lambda *a, **k: _Client(_Resp(payload)))
    result = await router.search_uniprot(UniprotSearchRequest(query="enzyme"))
    assert result["count"] == 1
    assert result["results"][0]["name"] == "Submitted enzyme name"
    assert result["results"][0]["reviewed"] is False


@pytest.mark.asyncio
async def test_cds_is_fetched_only_after_documented_uniprot_cross_reference(monkeypatch):
    async def fake_uniprot(_input):
        return {
            "accession": "P00533",
            "source": "UniProtKB",
            "entry_version": 210,
            "cds_accessions": [{
                "database": "EMBL",
                "accession": "X00588",
                "protein_sequence_id": "CAA25240.1",
                "nucleotide_sequence_id": "",
            }],
        }

    calls = []

    async def fake_ncbi(accession):
        calls.append(accession)
        return {
            "sequence": "ATGAAATAG",
            "length": 9,
            "description": "verified nucleotide record",
            "organism": "Homo sapiens",
        }

    monkeypatch.setattr(router.uniprot_tool, "run", fake_uniprot)
    monkeypatch.setattr(router.ncbi_service, "fetch_by_accession", fake_ncbi)
    result = await router.fetch_uniprot_cds(
        UniprotCDSRequest(accession="P00533", embl_accession="X00588.1")
    )
    assert calls == ["X00588.1"]
    assert result["cross_reference_verified"] is True
    assert result["cross_reference"]["accession"] == "X00588"
    assert result["uniprot_entry_version"] == 210


@pytest.mark.asyncio
async def test_arbitrary_cds_pairing_is_rejected_before_ncbi_fetch(monkeypatch):
    async def fake_uniprot(_input):
        return {
            "accession": "P00533",
            "cds_accessions": [{"database": "EMBL", "accession": "X00588"}],
        }

    async def forbidden_ncbi(_accession):
        raise AssertionError("NCBI fetch must not occur for an unverified relationship")

    monkeypatch.setattr(router.uniprot_tool, "run", fake_uniprot)
    monkeypatch.setattr(router.ncbi_service, "fetch_by_accession", forbidden_ncbi)
    with pytest.raises(HTTPException) as exc:
        await router.fetch_uniprot_cds(
            UniprotCDSRequest(accession="P00533", embl_accession="NC_000001.11")
        )
    assert exc.value.status_code == 400
    assert "No CDS relationship was inferred" in exc.value.detail


def test_accession_version_matching_is_explicit_and_narrow():
    detail = {"cds_accessions": [{"database": "EMBL", "accession": "X00588"}]}
    assert router._matching_cds_crossref(detail, "X00588") is not None
    assert router._matching_cds_crossref(detail, "X00588.1") is not None
    assert router._matching_cds_crossref(detail, "X00589") is None
