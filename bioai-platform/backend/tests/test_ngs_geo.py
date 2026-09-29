"""GEO accession lookup keeps the accession exact and files attributable to NCBI."""

import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.routers import ngs_geo


def test_resolves_series_with_real_supplementary_names(monkeypatch):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"idlist": ["200047774"]}})
        if request.url.path.endswith("esummary.fcgi"):
            return httpx.Response(200, json={"result": {"200047774": {
                "accession": "GSE47774", "title": "RNA sequencing study", "gdstype": "Expression profiling by high throughput sequencing",
                "n_samples": 2, "suppfile": "TSV", "samples": [
                    {"accession": "GSM123", "title": "control"}, {"accession": "GSM124", "title": "case"}],
            }}})
        return httpx.Response(200, text='<a href="../">Parent</a><a href="GSE47774_counts.tsv.gz">counts</a><a href="https://evil.test/file">bad</a>')

    transport = httpx.MockTransport(respond)
    client = httpx.AsyncClient
    monkeypatch.setattr(ngs_geo.httpx, "AsyncClient", lambda **kwargs: client(transport=transport, **kwargs))
    result = asyncio.run(ngs_geo.resolve_geo("gse47774"))
    assert result["is_sequencing"] is True
    assert len(result["samples"]) == 2
    assert result["files"] == [{"name": "GSE47774_counts.tsv.gz", "url": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE47nnn/GSE47774/suppl/GSE47774_counts.tsv.gz"}]
    assert all("evil.test" not in url for url in requests)


def test_rejects_invalid_and_inexact_accessions(monkeypatch):
    with pytest.raises(HTTPException) as invalid:
        asyncio.run(ngs_geo.resolve_geo("https://other.example/GSE123"))
    assert invalid.value.status_code == 422

    def respond(request):
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"idlist": ["123"]}})
        return httpx.Response(200, json={"result": {"123": {"accession": "GSE1234"}}})

    transport = httpx.MockTransport(respond)
    client = httpx.AsyncClient
    monkeypatch.setattr(ngs_geo.httpx, "AsyncClient", lambda **kwargs: client(transport=transport, **kwargs))
    with pytest.raises(HTTPException) as mismatch:
        asyncio.run(ngs_geo.resolve_geo("GSE123"))
    assert mismatch.value.status_code == 404
