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


async def _request_with_retry(method: str, url: str, max_retries: int = 3, request_timeout: float = 60.0, **kwargs) -> httpx.Response:
    """Make an HTTP request with retry on connection, timeout, and transient errors.

    request_timeout is the read/write timeout. NCBI's synchronous mode blocks
    until results are ready, so callers must pass a generous value for it.
    """
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(request_timeout, connect=15.0)) as client:
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

    resp = await _request_with_retry(
        "post", NCBI_BLAST_URL, data=params,
        request_timeout=300.0 if not async_flag else 60.0,
    )
    text = resp.text

    rid_match = re.search(r"RID\s*=\s*(\S+)", text)
    rtoe_match = re.search(r"RTOE\s*=\s*(\d+)", text)

    if not rid_match:
        return {"error": "No RID returned from NCBI", "raw": text[:500]}

    rid = rid_match.group(1)
    rtoe = int(rtoe_match.group(1)) if rtoe_match else 60

    result = {"rid": rid, "estimated_seconds": rtoe}
    if not async_flag and "Status=READY" in text:
        result["raw"] = text
    return result


async def submit_blast_sync(sequence: str, **kwargs) -> dict:
    """Legacy synchronous BLAST helper.

    Kept for compatibility with tests and callers, but production retry logic
    intentionally avoids this path because a blocking request can outlive the
    job's wall-clock deadline.
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
    """Poll NCBI with exponential backoff until READY or budget exhausted."""
    elapsed = 0
    delay = 5 if NCBI_API_KEY else 10
    consecutive_failures = 0
    max_consecutive_failures = 3
    stuck_threshold = max(estimated_seconds * 5, max_wait_seconds // 2)
    stuck_threshold = min(stuck_threshold, max_wait_seconds)

    while elapsed < max_wait_seconds:
        try:
            result = await check_status(rid)
            consecutive_failures = 0
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
            delay = min(delay * 1.5, 15 if NCBI_API_KEY else 25)
            continue

        status = result["status"]

        if status == "READY":
            return result
        if status not in ("WAITING", "UNKNOWN", "QUEUED"):
            logger.warning("BLAST RID %s returned terminal status: %s", rid, status)
            return result

        if elapsed > stuck_threshold:
            logger.warning(
                "BLAST RID %s stuck in %s for %ds (threshold=%ds), treating as STUCK",
                rid, status, elapsed, stuck_threshold,
            )
            return {"status": "STUCK", "rid": rid, "error": f"Job stuck in {status} for {elapsed}s"}

        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 15 if NCBI_API_KEY else 25)

    logger.warning("BLAST RID %s timed out after %ds", rid, max_wait_seconds)
    return {"status": "TIMEOUT", "rid": rid}


async def run_blast_with_retry(
    sequence: str,
    retries: int = 2,
    max_wait_seconds: int = 600,
    **submit_kwargs,
) -> dict:
    """Submit, poll and fetch BLAST results with a bounded runtime.

    Production retries remain asynchronous. The previous synchronous retry
    path could block for 300 seconds per HTTP attempt and therefore exceed the
    advertised hard deadline. We cap both retry count and poll budget so a
    degraded NCBI service cannot leave a BioNexus job apparently frozen.
    """
    last_error = None
    MAX_RTOE = 90

    # The pipeline already has EBI as its primary BLAST provider. NCBI is the
    # fallback, so fail it promptly enough for the overall job to terminate
    # cleanly instead of consuming tens of minutes on repeated QBLAST waits.
    retries = min(max(int(retries), 0), 1)
    max_wait_seconds = min(max(int(max_wait_seconds), 60), 300)
    HARD_DEADLINE_S = max_wait_seconds + 120

    import time
    t0 = time.monotonic()

    for attempt in range(retries + 1):
        elapsed = time.monotonic() - t0
        if elapsed >= HARD_DEADLINE_S:
            logger.warning(
                "BLAST hard deadline reached (%.0fs / %ds) — aborting before attempt %d",
                elapsed, HARD_DEADLINE_S, attempt + 1,
            )
            return {"error": f"BLAST hard deadline ({HARD_DEADLINE_S}s) exceeded after {elapsed:.0f}s"}

        # Never switch to synchronous QBLAST here. A blocking sync request can
        # outlive the wall-clock budget before control returns to this loop.
        try:
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
            "BLAST submitted (attempt %d/%d), RID=%s, est=%ds",
            attempt + 1, retries + 1, rid, est,
        )

        if est > MAX_RTOE:
            logger.warning(
                "BLAST RTOE=%ds exceeds threshold (%ds) — abandoning NCBI fallback",
                est, MAX_RTOE,
            )
            return {"error": f"NCBI estimated {est}s queue time (threshold {MAX_RTOE}s)"}

        remaining = HARD_DEADLINE_S - (time.monotonic() - t0)
        per_attempt_budget = min(max_wait_seconds, int(remaining) - 30)
        if per_attempt_budget < 30:
            logger.warning("BLAST: only %.0fs left of hard deadline, skipping poll", remaining)
            last_error = f"BLAST: insufficient time remaining ({remaining:.0f}s) for poll"
            continue

        try:
            status_result = await check_status_until_ready(
                rid, max_wait_seconds=per_attempt_budget, estimated_seconds=est,
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
