"""Page capture service — techspec.md §3.

For every external source a pipeline run queries, capture the *human-facing*
page (not just the API endpoint): page title, readable text sections and
figure image URLs. Rows land in `page_captures` keyed by (job_id, source) so
the final synthesis can cite real pages.

Safety: every fetch goes through `ssrf.validate_url()` (allowlist) and a
per-host rate limiter. Captures are strictly best-effort — they must never
break a pipeline run.
"""

import asyncio
import html as htmllib
import logging
import re
import time

import httpx

from app.services.ssrf import validate_url

logger = logging.getLogger(__name__)

# Minimum delay between consecutive fetches of the same host.
MIN_INTERVAL_S = 1.5
_host_lock = asyncio.Lock()
_last_hit: dict[str, float] = {}

_MAX_SECTIONS = 8
_SECTION_CHARS = 600
_TIMEOUT_S = 20

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"<h([23])\b[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_IMG_RE = re.compile(r'<img\b[^>]*?\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
_OG_IMAGE_RE = re.compile(
    r'<meta\s+[^>]*?property=["\']og:image["\'][^>]*?content=["\']([^"\']+)["\']', re.IGNORECASE
)


def _clean(text: str) -> str:
    return htmllib.unescape(re.sub(r"\s+", " ", _TAG_RE.sub("", text))).strip()


def extract_page_content(html: str) -> dict:
    """Stdlib-only extraction: title, heading-led text sections, figure URLs."""
    body = _SCRIPT_RE.sub("", html)

    title_match = _TITLE_RE.search(body)
    title = _clean(title_match.group(1)) if title_match else None

    figure_urls: list[str] = []
    og = _OG_IMAGE_RE.search(body)
    if og:
        figure_urls.append(og.group(1))
    for fig_block in re.findall(r"<figure\b[^>]*>(.*?)</figure>", body, re.IGNORECASE | re.DOTALL):
        for src in _IMG_RE.findall(fig_block)[:3]:
            if src.startswith("http") and src not in figure_urls:
                figure_urls.append(src)

    sections: list[dict] = []
    headings = list(_HEADING_RE.finditer(body))
    for i, match in enumerate(headings):
        if len(sections) >= _MAX_SECTIONS:
            break
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else min(len(body), start + 4000)
        text = _clean(body[start:end])[:_SECTION_CHARS]
        if text:
            sections.append({"heading": _clean(match.group(2))[:200], "text": text})

    if not sections and not headings:
        fallback = _clean(body)[:_SECTION_CHARS]
        if fallback:
            sections.append({"heading": None, "text": fallback})

    return {
        "title": title,
        "text_sections": sections,
        "figure_urls": figure_urls[:6],
    }


async def _throttle(host: str) -> None:
    async with _host_lock:
        now = time.monotonic()
        last = _last_hit.get(host)
        wait = 0.0 if last is None else max(0.0, MIN_INTERVAL_S - (now - last))
        _last_hit[host] = now + wait
    if wait > 0:
        await asyncio.sleep(wait)


def _get_supabase():
    from app.services.supabase import get_client

    return get_client()


async def capture_page(
    job_id: str,
    source: str,
    page_url: str,
    user_id: str | None = None,
) -> dict | None:
    """Fetch + store one page capture. Never raises."""
    row = {"job_id": job_id, "source": source, "page_url": page_url, "user_id": user_id}
    try:
        validate_url(page_url)
        host = httpx.URL(page_url).host
        await _throttle(host)
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
            res = await client.get(page_url, headers={"User-Agent": "BioNexus/1.0 (research tool)"})
        res.raise_for_status()
        extracted = extract_page_content(res.text)
        row.update(extracted, fetch_status="captured")
    except Exception as exc:
        logger.info("Page capture %s/%s failed: %s", job_id, source, exc)
        row.update(fetch_status="failed", error_note=str(exc)[:300])

    try:
        (
            _get_supabase()
            .table("page_captures")
            .upsert(row, on_conflict="job_id,source")
            .execute()
        )
    except Exception as exc:
        logger.warning("Could not persist page capture %s/%s: %s", job_id, source, exc)
    return row


def capture_bg(job_id: str, source: str, page_url: str, user_id: str | None = None):
    """Fire-and-forget capture for pipeline steps (never blocks the run)."""
    if not job_id or "-" not in str(job_id):  # skip test/in-memory ids
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(capture_page(job_id, source, page_url, user_id))
    except RuntimeError:
        logger.debug("No running loop for capture %s/%s", job_id, source)
