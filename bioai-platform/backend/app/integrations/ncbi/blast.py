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

from app.config import settings

NCBI_API_KEY = settings.NCBI_API_KEY


def _api_key_param() -> dict:
    """Return {api_key: key} if configured, else empty dict."""
    return {"api_key": NCBI_API_KEY} if NCBI_API_KEY else {}


async def _request_with_retry(method: str, url: str, max_retries: int = 3, **kwargs) -> httpx.Response:
    """Make an HTTP request with retry on connection, timeout, and transient errors."""
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                resp = await getattr(client, method)(url, **kwargs)
                resp.raise_for_status()
                return resp
        except (
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
        ) as e:
            if attempt < max_retries - 1:
                delay = 3 * (attempt + 1)
                logger.warning("NCBI request failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, e, delay)
                await asyncio.sleep(delay)
            else:
                raise


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
        "EMAIL": settings.NCBI_EMAIL,
        **_api_key_param(),
    }
    if gapopen > 0:
        params["GAPOPEN"] = str(gapopen)
    if gapextend > 0:
        params["GAPEXTEND"] = str(gapextend)

    resp = await _request_with_retry("post", NCBI_BLAST_URL, data=params)
    text = resp.text

    rid_match = re.search(r"RID\s*=\s*(\S+)", text)
    rtoe_match = re.search(r"RTOE\s*=\s*(\d+)", text)

    if not rid_match:
        return {"error": "No RID returned from NCBI", "raw": text[:500]}

    rid = rid_match.group(1)
    rtoe = int(rtoe_match.group(1)) if rtoe_match else 60

    return {"rid": rid, "estimated_seconds": rtoe}


async def submit_blast_sync(sequence: str, **kwargs) -> dict:
    """Submit BLAST in synchronous (blocking) mode — NCBI returns results inline.

    Used as fallback when async mode yields unreasonable RTOE or jobs get stuck.
    """
    kwargs.pop("async_flag", None)
    return await submit_blast(sequence, async_flag=False, **kwargs)


async def check_status(rid: str, fmt: str = "XML") -> dict:
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid, **_api_key_param()}
    resp = await _request_with_retry("get", NCBI_BLAST_URL, params=params)
    text = resp.text

    if "Status=" in text:
        status_match = re.search(r"Status\s*=\s*(\w+)", text)
        status = status_match.group(1) if status_match else "UNKNOWN"
    else:
        status = "READY"

    return {"status": status, "raw": text, "rid": rid}


async def fetch_results(rid: str, fmt: str = "XML") -> dict:
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid, **_api_key_param()}
    resp = await _request_with_retry("get", NCBI_BLAST_URL, params=params)
    text = resp.text

    if "Status=" in text and "Status=READY" not in text:
        return {"error": "Results not ready", "raw": text[:200]}

    return {"raw": text, "rid": rid}


async def check_status_until_ready(
    rid: str,
    max_wait_seconds: int = 300,
    estimated_seconds: int = 0,
) -> dict:
    """Poll NCBI with exponential backoff until READY or budget exhausted.

    Starts at 10s delay (NCBI rate-limit guidance: 1 req/10s without API key),
    backs off to 25s ceiling.  Transient poll failures (timeouts, HTTP errors)
    are tolerated up to 3 consecutive times before giving up.

    If estimated_seconds is provided and the job stays in WAITING for more
    than 5x that duration (minimum 60s), it's treated as stuck.
    """
    elapsed = 0
    delay = 10  # NCBI rate limit: 1 req/10s without API key
    consecutive_failures = 0
    max_consecutive_failures = 3
    # Stuck-job threshold: 5x the RTOE, but at least 60s
    stuck_threshold = max(estimated_seconds * 5, 60) if estimated_seconds > 0 else 120

    while elapsed < max_wait_seconds:
        try:
            result = await check_status(rid)
            consecutive_failures = 0  # reset on success
        except Exception as e:
            consecutive_failures += 1
            logger.warning(
                "BLAST poll for %s failed (consecutive %d/%d): %s",
                rid, consecutive_failures, max_consecutive_failures, e,
            )
            if consecutive_failures >= max_consecutive_failures:
                logger.warning(
                    "BLAST RID %s — %d consecutive poll failures, giving up", rid, consecutive_failures
                )
                return {"status": "POLL_FAILED", "rid": rid, "error": str(e)}
            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 1.5, 25)
            continue

        status = result["status"]

        if status == "READY":
            return result
        if status not in ("WAITING", "UNKNOWN", "QUEUED"):
            # FAILED / ERROR — bail immediately
            logger.warning("BLAST RID %s returned terminal status: %s", rid, status)
            return result

        # Stuck-job detection: if WAITING far beyond RTOE, job is likely stuck
        if elapsed > stuck_threshold:
            logger.warning(
                "BLAST RID %s stuck in %s for %ds (threshold=%ds), treating as STUCK",
                rid, status, elapsed, stuck_threshold,
            )
            return {"status": "STUCK", "rid": rid, "error": f"Job stuck in {status} for {elapsed}s"}

        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 25)  # back off, cap at 25s

    logger.warning("BLAST RID %s timed out after %ds", rid, max_wait_seconds)
    return {"status": "TIMEOUT", "rid": rid}


async def run_blast_with_retry(
    sequence: str,
    retries: int = 2,
    max_wait_seconds: int = 600,
    **submit_kwargs,
) -> dict:
    """Submit + poll + fetch with retries on timeout/failure.

    If NCBI dropped/lost the RID, no amount of polling helps — a fresh
    submit_blast() is the right fix.  retries=2 means 3 total attempts.

    Falls back to synchronous mode when async RTOE is unreasonable (>300s),
    which indicates NCBI server overload.  In sync mode NCBI blocks until
    results are ready (up to the httpx timeout).
    """
    last_error = None
    MAX_RTOE = 300  # if RTOE exceeds this, switch to sync mode

    for attempt in range(retries + 1):
        # On retry after stuck/timeout, try sync mode first
        use_sync = attempt > 0

        try:
            if use_sync:
                logger.info("BLAST attempt %d/%d: trying synchronous mode", attempt + 1, retries + 1)
                submit_result = await submit_blast_sync(sequence, **submit_kwargs)
            else:
                submit_result = await submit_blast(sequence, **submit_kwargs)
        except Exception as e:
            last_error = f"BLAST submit request failed: {e}"
            logger.warning(
                "BLAST submit threw (attempt %d/%d): %s",
                attempt + 1, retries + 1, last_error,
            )
            if attempt < retries:
                await asyncio.sleep(5 * (attempt + 1))
            continue

        if "error" in submit_result:
            last_error = submit_result["error"]
            logger.warning(
                "BLAST submit failed (attempt %d/%d): %s",
                attempt + 1, retries + 1, last_error,
            )
            if attempt < retries:
                await asyncio.sleep(5 * (attempt + 1))
            continue

        rid = submit_result["rid"]
        est = submit_result.get("estimated_seconds", 0)
        logger.info(
            "BLAST submitted (attempt %d/%d, sync=%s), RID=%s, est=%ds",
            attempt + 1, retries + 1, use_sync, rid, est,
        )

        # Detect unreasonable RTOE — switch to sync on next attempt
        if not use_sync and est > MAX_RTOE:
            logger.warning(
                "BLAST RTOE=%ds exceeds threshold (%ds), will use sync mode on retry", est, MAX_RTOE,
            )
            last_error = f"NCBI estimated {est}s queue time (threshold {MAX_RTOE}s)"
            if attempt < retries:
                await asyncio.sleep(2)
            continue

        if use_sync:
            # Sync mode: NCBI blocked and returned the result inline in the submit response.
            # The response text in submit_result may contain the XML already.
            # We need to poll once to check if it's actually ready.
            pass

        try:
            status_result = await check_status_until_ready(
                rid, max_wait_seconds=max_wait_seconds, estimated_seconds=est,
            )
        except Exception as e:
            last_error = f"BLAST polling crashed: {e}"
            logger.warning("BLAST RID %s: %s", rid, last_error)
            if attempt < retries:
                await asyncio.sleep(5 * (attempt + 1))
            continue

        if status_result["status"] == "READY":
            try:
                return await fetch_results(rid)
            except Exception as e:
                last_error = f"BLAST result fetch failed: {e}"
                logger.warning("BLAST RID %s: %s", rid, last_error)
                if attempt < retries:
                    await asyncio.sleep(5 * (attempt + 1))
                continue

        last_error = f"BLAST {status_result['status']} after polling (attempt {attempt + 1}/{retries + 1})"
        if status_result.get("error"):
            last_error += f": {status_result['error']}"
        logger.warning("BLAST RID %s: %s", rid, last_error)
        if attempt < retries:
            await asyncio.sleep(5 * (attempt + 1))

    return {"error": last_error or "BLAST failed after all attempts"}
