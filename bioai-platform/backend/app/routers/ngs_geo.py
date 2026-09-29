"""Resolve public GEO accessions into inspectable NGS input provenance.

GEO records describe experiments; they do not necessarily contain sequencing reads
or an integer count matrix suitable for statistical analysis.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import quote, unquote

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/ngs/v2/geo", tags=["ngs-v2-geo"])
_ACCESSION = re.compile(r"^(GSE|GSM|GDS|GPL)[0-9]{1,9}$", re.IGNORECASE)
_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class _DirectoryLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        name = unquote(href)
        if name and name not in ("../", "./") and "/" not in name and "\\" not in name and "?" not in name:
            self.names.append(name)


async def _supplementary_files(client: httpx.AsyncClient, accession: str) -> list[dict[str, str]]:
    if not accession.startswith(("GSE", "GSM")):
        return []
    prefix, digits = accession[:3], accession[3:]
    block = f"{prefix}{digits[:-3]}nnn" if len(digits) > 3 else f"{prefix}nnn"
    base = f"https://ftp.ncbi.nlm.nih.gov/geo/{'series' if prefix == 'GSE' else 'samples'}/{block}/{accession}/suppl/"
    try:
        response = await client.get(base)
        response.raise_for_status()
        parser = _DirectoryLinks()
        parser.feed(response.text[:500_000])
        return [{"name": name, "url": base + quote(name)} for name in dict.fromkeys(parser.names) if not name.endswith("/")][:40]
    except (httpx.HTTPError, ValueError):
        return []


def _files(value: object) -> list[dict[str, str]]:
    if not isinstance(value, str):
        return []
    # ESummary supplementary files are delimited by semicolons on GEO records.
    urls = re.findall(r"https?://[^\s;,|<>]+", value)
    return [
        {"name": url.rsplit("/", 1)[-1], "url": url}
        for url in urls[:40]
        if url.startswith(("https://ftp.ncbi.nlm.nih.gov/", "https://www.ncbi.nlm.nih.gov/", "https://ftp-trace.ncbi.nlm.nih.gov/"))
    ]


@router.get("/{accession}")
async def resolve_geo(accession: str):
    accession = accession.strip().upper()
    if not _ACCESSION.fullmatch(accession):
        raise HTTPException(422, "Enter a GEO accession such as GSE12345, GSM12345, GDS1234, or GPL1234.")
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            search = await client.get(f"{_EUTILS}/esearch.fcgi", params={
                "db": "gds", "term": f"{accession}[ACCN]", "retmode": "json", "retmax": 5,
                "tool": "bionexus",
            })
            search.raise_for_status()
            ids = search.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                raise HTTPException(404, f"No public GEO record was found for {accession}.")
            summary = await client.get(f"{_EUTILS}/esummary.fcgi", params={
                "db": "gds", "id": ",".join(ids), "retmode": "json", "tool": "bionexus",
            })
            summary.raise_for_status()
            result = summary.json().get("result", {})
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(502, "GEO is temporarily unavailable. Try the accession again shortly.") from exc

    record = next((result.get(uid) for uid in ids if isinstance(result.get(uid), dict)
                   and str(result[uid].get("accession", "")).upper() == accession), None)
    if record is None:
        raise HTTPException(404, f"No exact public GEO record was found for {accession}.")

    samples = [
        {"accession": sample["accession"], "title": str(sample.get("title", ""))[:300]}
        for sample in record.get("samples", [])[:200]
        if isinstance(sample, dict) and re.fullmatch(r"GSM[0-9]+", str(sample.get("accession", "")))
    ] if isinstance(record.get("samples"), list) else []
    relations = [
        {"name": str(relation.get("name", ""))[:80], "target": str(relation.get("target", ""))[:80]}
        for relation in record.get("extrelations", record.get("relations", []))[:30]
        if isinstance(relation, dict)
    ] if isinstance(record.get("extrelations", record.get("relations", [])), list) else []
    assay = str(record.get("gdstype", record.get("gdsType", "")))[:200]
    # ESummary's suppfile often contains only extensions (e.g. "CSV"), not URLs.
    # Enumerate the public accession directory to show actual downloadable files.
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        files = await _supplementary_files(client, accession)
    if not files:
        files = _files(record.get("suppfile", record.get("suppFile", "")))
    return {
        "accession": accession,
        "kind": accession[:3],
        "title": str(record.get("title", ""))[:500],
        "summary": str(record.get("summary", ""))[:2000],
        "assay": assay,
        "organism": str(record.get("taxon", record.get("taxonname", "")))[:160],
        "samples": samples,
        "sample_count": int(record.get("n_samples", record.get("nSamples", len(samples))) or len(samples)),
        "files": files,
        "relations": relations,
        "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}",
        "is_sequencing": "high throughput sequencing" in assay.lower() or "sequencing" in assay.lower(),
    }
