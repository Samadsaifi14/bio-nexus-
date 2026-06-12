"""
Thin client for NCBI BLAST URL API (QBLAST).

Rate limit: NCBI enforces 1 request per 10 seconds without an API key,
3 req/s with an API key. Rate limiting is the caller's responsibility.

API docs: https://ncbi.github.io/blast-cloud/api.html
"""

import re
import httpx
from typing import Optional

NCBI_BLAST_URL = "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi"
RATE_LIMIT_SECONDS = 10


async def submit_blast(
    sequence: str,
    program: str = "blastp",
    database: str = "nr",
    hitlist_size: int = 100,
    expect: float = 10.0,
    gapopen: int = -1,
    gapextend: int = -1,
    matrix: str = "BLOSUM62",
    async_flag: bool = True,
) -> dict:
    params = {
        "CMD": "Put",
        "PROGRAM": program,
        "DATABASE": database,
        "QUERY": sequence,
        "HITLIST_SIZE": str(hitlist_size),
        "EXPECT": str(expect),
        "MATRIX": matrix,
        "ASYNC": "1" if async_flag else "0",
    }
    if gapopen > 0:
        params["GAPOPEN"] = str(gapopen)
    if gapextend > 0:
        params["GAPEXTEND"] = str(gapextend)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(NCBI_BLAST_URL, data=params)
        resp.raise_for_status()
        text = resp.text

    rid_match = re.search(r"RID\s*=\s*(\S+)", text)
    rtoe_match = re.search(r"RTOE\s*=\s*(\d+)", text)

    if not rid_match:
        return {"error": "No RID returned from NCBI", "raw": text[:500]}

    rid = rid_match.group(1)
    rtoe = int(rtoe_match.group(1)) if rtoe_match else 60

    return {"rid": rid, "estimated_seconds": rtoe}


async def check_status(rid: str, fmt: str = "XML") -> dict:
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(NCBI_BLAST_URL, params=params)
        resp.raise_for_status()
        text = resp.text

    if "Status=" in text:
        status_match = re.search(r"Status\s*=\s*(\w+)", text)
        status = status_match.group(1) if status_match else "UNKNOWN"
    else:
        status = "READY"

    return {"status": status, "raw": text, "rid": rid}


async def fetch_results(rid: str, fmt: str = "XML") -> dict:
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(NCBI_BLAST_URL, params=params)
        resp.raise_for_status()
        text = resp.text

    if "Status=" in text and "Status=READY" not in text:
        return {"error": "Results not ready", "raw": text[:200]}

    return {"raw": text, "rid": rid}
