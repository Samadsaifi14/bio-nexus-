"""GEO Series discovery. Results are links to source records, never count matrices."""
from __future__ import annotations

import re

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/ngs/v2/geo", tags=["geo-discovery"])
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@router.get("/search")
async def search_geo(q: str = Query(min_length=2, max_length=120)):
    query = q.strip()
    if not query:
        raise HTTPException(422, "Enter a GEO accession or search terms.")
    term = f"{query.upper()}[ACCN]" if re.fullmatch(r"GSE\d+", query, re.I) else f"({query}) AND gse[ETYP]"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            search = (await client.get(f"{BASE}/esearch.fcgi", params={"db": "gds", "term": term, "retmode": "json", "retmax": 20, "tool": "BioNexus"}))
            search.raise_for_status()
            ids = search.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return {"query": query, "results": []}
            summary = await client.get(f"{BASE}/esummary.fcgi", params={"db": "gds", "id": ",".join(ids), "retmode": "json", "tool": "BioNexus"})
            summary.raise_for_status()
            records = summary.json().get("result", {})
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(502, "NCBI GEO is unavailable. Try again shortly.") from exc
    results = []
    for uid in ids:
        record = records.get(str(uid), {})
        accession = str(record.get("accession", ""))
        if not re.fullmatch(r"GSE\d+", accession, re.I):
            continue
        results.append({
            "accession": accession,
            "title": record.get("title", ""),
            "summary": str(record.get("summary", ""))[:600],
            "sample_count": record.get("n_samples"),
            "organism": record.get("taxon", ""),
            "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}",
        })
    return {"query": query, "results": results}
