"""
Thin client for NCBI BLAST URL API (QBLAST).

Rate limit: no more than one request per 10 seconds, and poll each RID
at most once per minute. API keys do not relax BLAST usage guidelines.
Cross-worker request coordination remains the caller's responsibility.

API docs: https://ncbi.github.io/blast-cloud/api.html
"""

import asyncio
import logging
import os
import re
from time import monotonic
import httpx

logger = logging.getLogger(__name__)

NCBI_BLAST_URL = "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi"
RATE_LIMIT_SECONDS = 10

from app.config import settings

NCBI_API_KEY = settings.NCBI_API_KEY


def _api_key_param() -> dict:
    """Return {api_key: key} if configured, else empty dict."""
    return {"api_key": NCBI_API_KEY} if NCBI_API_KEY else {}


class NCBIUnavailableError(RuntimeError):
    """NCBI returned a temporary outage message, even with HTTP 200."""


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
                if resp.text.strip().casefold() in ("temporarily unavailable", "service temporarily unavailable"):
                    raise NCBIUnavailableError("NCBI service temporarily unavailable")
                return resp
        except (
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
            NCBIUnavailableError,
        ) as e:
            if attempt < max_retries - 1:
                delay = 10 * (attempt + 1)
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
    # Reject malformed queries before spending a remote submission/poll budget.
    # FASTA headers and whitespace are permitted; valid ambiguous residues stay.
    sequence = "".join(line.strip() for line in str(sequence).splitlines()
                       if not line.lstrip().startswith(">"))
    sequence = re.sub(r"\s+", "", sequence).upper()
    alphabet = ("ACGTURYSWKMBDHVN" if program in ("blastn", "blastx", "tblastx")
                else "ACDEFGHIKLMNPQRSTVWYBXZJUO*")
    if not sequence or any(char not in alphabet for char in sequence):
        return {"error": "BLAST query is empty or contains invalid sequence characters",
                "status": "INVALID_QUERY", "search_complete": False}
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


async def check_status(rid: str, fmt: str = "XML2_S") -> dict:
    params = {"CMD": "Get", "FORMAT_TYPE": fmt, "RID": rid, **_api_key_param()}
    resp = await _request_with_retry("get", NCBI_BLAST_URL, params=params, max_retries=1)
    text = resp.text
    match = re.search(r"Status\s*=\s*(\w+)", text, flags=re.IGNORECASE)
    status = match.group(1).upper() if match else "UNKNOWN"
    if match is None:
        # An absent status line means readiness only for an actual BLAST XML
        # document. A proxy error or HTML service page is never a ready search.
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(text)
            if root.tag.rsplit("}", 1)[-1] in ("BlastOutput", "BlastXML2", "BlastOutput2"):
                status = "READY"
        except ET.ParseError:
            pass
    return {"status": status, "raw": text, "rid": rid}


async def fetch_results(rid: str, fmt: str = "XML2_S") -> dict:
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
    """Poll a RID at most once per minute within a wall-clock budget.

    WAITING is not proof that a search is stuck. Keep the accepted request
    alive for its full budget instead of abandoning it halfway through.
    https://blast.ncbi.nlm.nih.gov/doc/blast-help/developerinfo.html
    """
    deadline = monotonic() + max_wait_seconds
    consecutive_failures = 0
    delay = max(60, estimated_seconds)
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {"status": "TIMEOUT", "rid": rid}
        await asyncio.sleep(min(delay, remaining))
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {"status": "TIMEOUT", "rid": rid}
        try:
            result = await asyncio.wait_for(check_status(rid), timeout=remaining)
            consecutive_failures = 0
        except asyncio.TimeoutError:
            return {"status": "TIMEOUT", "rid": rid}
        except Exception as exc:
            consecutive_failures += 1
            logger.warning("BLAST poll for %s failed (%d/3): %s", rid, consecutive_failures, exc)
            if consecutive_failures >= 3:
                return {"status": "POLL_FAILED", "rid": rid, "error": str(exc)}
            delay = 60
            continue
        status = result["status"]
        if status not in ("WAITING", "UNKNOWN", "QUEUED"):
            return result
        delay = 60


async def _run_blast_attempts(
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
                await asyncio.sleep(RATE_LIMIT_SECONDS * (attempt + 1))
            continue

        if "error" in submit_result:
            last_error = submit_result["error"]
            logger.warning(
                "BLAST submit failed (attempt %d/%d): %s",
                attempt + 1, retries + 1, last_error,
            )
            if attempt < retries:
                await asyncio.sleep(RATE_LIMIT_SECONDS * (attempt + 1))
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
                await asyncio.sleep(RATE_LIMIT_SECONDS * (attempt + 1))
            continue

        if status_result["status"] == "READY":
            try:
                from app.integrations.ncbi.parser import parse_blast_xml
                raw = status_result.get("raw", "")
                if raw and "error" not in parse_blast_xml(raw):
                    return {"raw": raw, "rid": rid}
                await asyncio.sleep(RATE_LIMIT_SECONDS)
                return await fetch_results(rid)
            except Exception as e:
                last_error = f"BLAST result fetch failed: {e}"
                logger.warning("BLAST RID %s: %s", rid, last_error)
                if attempt < retries:
                    await asyncio.sleep(RATE_LIMIT_SECONDS * (attempt + 1))
                continue

        if status_result["status"] == "TIMEOUT":
            # A queued search is still an accepted remote job. Resubmitting the
            # same query discards its queue position and creates orphaned RIDs.
            return {"error": "NCBI search did not complete within the polling budget",
                    "status": "TIMEOUT", "rid": rid, "search_complete": False}

        last_error = f"BLAST {status_result['status']} after polling (attempt {attempt + 1}/{retries + 1})"
        if status_result.get("error"):
            last_error += f": {status_result['error']}"
        logger.warning("BLAST RID %s: %s", rid, last_error)
        if attempt < retries:
            await asyncio.sleep(RATE_LIMIT_SECONDS * (attempt + 1))

    return {"error": last_error or "BLAST failed after all attempts"}


async def run_blast_with_retry(
    sequence: str,
    retries: int = 2,
    max_wait_seconds: int = 600,
    **submit_kwargs,
) -> dict:
    """Enforce the advertised wall-clock budget across every HTTP phase.

    Poll counters alone do not include HTTP retries or result downloads.
    Cancellation of this enclosing task also cancels the active HTTP request.
    """
    poll_budget = min(max(int(max_wait_seconds), 60), 300)
    hard_budget = poll_budget + 120
    try:
        return await asyncio.wait_for(
            _run_blast_attempts(sequence, retries=retries,
                                max_wait_seconds=poll_budget, **submit_kwargs),
            timeout=hard_budget,
        )
    except asyncio.TimeoutError:
        return {"error": f"BLAST hard deadline ({hard_budget}s) exceeded",
                "status": "TIMEOUT", "search_complete": False}
