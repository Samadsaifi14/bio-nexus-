"""
Thin client for NCBI BLAST URL API (QBLAST).

Rate limit: NCBI enforces 1 request per 10 seconds without an API key,
3 req/s with an API key. Rate limiting is the caller's responsibility.

API docs: https://ncbi.github.io/blast-cloud/api.html
"""

import asyncio
import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)

NCBI_BLAST_URL = "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi"
RATE_LIMIT_SECONDS = 10

# NCBI API key — free tier gives 3 req/s instead of 1 req/10s.
# Set NCBI_API_KEY env var in .env or HF Spaces secrets.
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")


def _api_key_param() -> dict:
    """Return {api_key: key} if configured, else empty dict."""
    return {"api_key": NCBI_API_KEY} if NCBI_API_KEY else {}


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
        **_api_key_param(),
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
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid, **_api_key_param()}
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=10.0)) as client:
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
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid, **_api_key_param()}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(NCBI_BLAST_URL, params=params)
        resp.raise_for_status()
        text = resp.text

    if "Status=" in text and "Status=READY" not in text:
        return {"error": "Results not ready", "raw": text[:200]}

    return {"raw": text, "rid": rid}


async def check_status_until_ready(
    rid: str,
    max_wait_seconds: int = 300,
) -> dict:
    """Poll NCBI with exponential backoff until READY or budget exhausted.

    Starts at 5s delay (NCBI guidance), backs off to 20s ceiling.
    Returns early on ERROR/FAILED — no point polling a dead RID.
    """
    elapsed = 0
    delay = 5  # start at 5s, matches NCBI's own guidance

    while elapsed < max_wait_seconds:
        result = await check_status(rid)
        status = result["status"]

        if status == "READY":
            return result
        if status not in ("WAITING", "UNKNOWN"):
            # FAILED / ERROR — bail immediately
            logger.warning("BLAST RID %s returned terminal status: %s", rid, status)
            return result

        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 20)  # back off, cap at 20s

    logger.warning("BLAST RID %s timed out after %ds", rid, max_wait_seconds)
    return {"status": "TIMEOUT", "rid": rid}


async def run_blast_with_retry(
    sequence: str,
    retries: int = 1,
    max_wait_seconds: int = 300,
    **submit_kwargs,
) -> dict:
    """Submit + poll + fetch with one retry on timeout/failure.

    If NCBI dropped/lost the RID, no amount of polling helps — a fresh
    submit_blast() is the right fix.  retries=1 means 2 total attempts
    (NCBI asks callers not to hammer the API).
    """
    last_error = None

    for attempt in range(retries + 1):
        submit_result = await submit_blast(sequence, **submit_kwargs)
        if "error" in submit_result:
            last_error = submit_result["error"]
            logger.warning(
                "BLAST submit failed (attempt %d/%d): %s",
                attempt + 1, retries + 1, last_error,
            )
            continue

        rid = submit_result["rid"]
        logger.info(
            "BLAST submitted (attempt %d/%d), RID=%s, est=%ds",
            attempt + 1, retries + 1, rid, submit_result.get("estimated_seconds", 0),
        )

        status_result = await check_status_until_ready(rid, max_wait_seconds=max_wait_seconds)
        if status_result["status"] == "READY":
            return await fetch_results(rid)

        last_error = f"BLAST {status_result['status']} after polling (attempt {attempt + 1})"
        logger.warning("BLAST RID %s: %s", rid, last_error)

    return {"error": last_error or "BLAST failed after all attempts"}
