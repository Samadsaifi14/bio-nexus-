"""
Tests for 3c UniProt search polish:

- reviewed/organism filters are folded into the UniProt query string
- search results carry a `reviewed` flag derived from entryType

Network calls are mocked; these run fully offline.
"""

import pytest
from fastapi import HTTPException

from app.routers import uniprot as uniprot_router
from app.routers.uniprot import UniprotSearchRequest, search_uniprot


class FakeResp:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params=None, **kwargs):
        self.calls.append((url, params))
        results = []
        for i in range(params.get("size", 1)):
            results.append({
                "primaryAccession": f"P{i:05d}",
                "proteinDescription": {"recommendedName": {"fullName": {"value": "Test protein"}}},
                "genes": [{"geneName": {"value": "TP53"}}],
                "organism": {"scientificName": "Homo sapiens"},
                "sequence": {"length": 100},
                "entryType": "UniProtKB reviewed (Swiss-Prot)",
            })
        return FakeResp(200, {"results": results})


@pytest.mark.asyncio
async def test_reviewed_and_organism_fold_into_query(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(uniprot_router.httpx, "AsyncClient", lambda *a, **k: fake)
    req = UniprotSearchRequest(query="p53", max_results=1, reviewed=True, organism="Homo sapiens")
    res = await search_uniprot(req)
    assert res["count"] == 1
    assert res["results"][0]["reviewed"] is True
    _, params = fake.calls[0]
    assert "AND organism_name:\"Homo sapiens\"" in params["query"]
    assert "AND reviewed:true" in params["query"]


@pytest.mark.asyncio
async def test_no_filters_query_unchanged(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(uniprot_router.httpx, "AsyncClient", lambda *a, **k: fake)
    req = UniprotSearchRequest(query="BRCA1")
    res = await search_uniprot(req)
    assert res["results"][0]["reviewed"] is True
    _, params = fake.calls[0]
    assert params["query"] == "BRCA1"


@pytest.mark.asyncio
async def test_reviewed_flag_false_for_trembl(monkeypatch):
    class FakeClientTrEmbl(FakeClient):
        async def get(self, url, params=None, **kwargs):
            self.calls.append((url, params))
            return FakeResp(200, {"results": [{
                "primaryAccession": "A0A1111111",
                "proteinDescription": {},
                "genes": [],
                "organism": {"scientificName": "Unknown"},
                "sequence": {"length": 50},
                "entryType": "UniProtKB unreviewed (TrEMBL)",
            }]})

    fake = FakeClientTrEmbl()
    monkeypatch.setattr(uniprot_router.httpx, "AsyncClient", lambda *a, **k: fake)
    req = UniprotSearchRequest(query="hypothetical")
    res = await search_uniprot(req)
    assert res["results"][0]["reviewed"] is False


@pytest.mark.asyncio
async def test_search_failure_raises_502(monkeypatch):
    class FakeClientFail(FakeClient):
        async def get(self, url, params=None, **kwargs):
            self.calls.append((url, params))
            return FakeResp(500, {})

    fake = FakeClientFail()
    monkeypatch.setattr(uniprot_router.httpx, "AsyncClient", lambda *a, **k: fake)
    with pytest.raises(HTTPException) as exc:
        await search_uniprot(UniprotSearchRequest(query="p53"))
    assert exc.value.status_code == 502
