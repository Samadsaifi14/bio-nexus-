"""GEO discovery retains source links without fabricating count data."""
import asyncio

import httpx

from app.routers import geo_search


def test_geo_series_search(monkeypatch):
    async def detail(client, accession):
        assert accession == "GSE336901"
        return {"accession": accession, "title": "RNA-seq study", "design": "Published data", "samples": [{}] * 8}

    monkeypatch.setattr(geo_search, "fetch_series", detail)
    response = asyncio.run(geo_search.search_geo("GSE336901"))
    assert response["results"] == [{
        "accession": "GSE336901", "title": "RNA-seq study", "summary": "Published data",
        "sample_count": 8, "organism": "", "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE336901",
    }]


def test_geo_search_excludes_non_series(monkeypatch):
    original_client = httpx.AsyncClient

    def respond(request):
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"idlist": ["123"]}})
        return httpx.Response(200, json={"result": {"123": {"accession": "GSM10", "title": "Sample"}}})

    monkeypatch.setattr(geo_search.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond)))
    assert asyncio.run(geo_search.search_geo("RNA-seq"))["results"] == []
