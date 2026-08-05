import asyncio
import json
import logging
import re
from typing import AsyncGenerator

from litellm import acompletion
from app.config import settings
from app.ai.llm_client import llm_client
from app.ai.prompts import get_prompt

logger = logging.getLogger(__name__)


def _retry_delay_seconds(error: BaseException) -> float | None:
    """Parse litellm/rate-limit errors of the form 'retry in 9.7s' or 'retry in 30 seconds'."""
    text = str(error)
    for pattern in (
        r"retry[^\d]{0,20}(\d+(?:\.\d+)?)\s*s\b",
        r"retry[^\d]{0,20}(\d+(?:\.\d+)?)\s+seconds?\b",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                delay = float(m.group(1))
                return min(max(delay, 1.0), 30.0)
            except ValueError:
                return None
    return None


def _is_model_missing(error: BaseException) -> bool:
    """True when the provider reports the model doesn't exist / isn't enabled —
    retrying it is pointless, so move on to the next provider immediately."""
    text = str(error).lower()
    return any(
        needle in text
        for needle in (
            "not found",
            "not support",
            "notfounderror",
            "modelnotfound",
            "models/",
            "is not found",
            "not accessible",
            "does not exist",
        )
    )


def _friendly_error(error: BaseException) -> str:
    text = str(error)
    if "organization_restricted" in text or "Organization has been restricted" in text:
        return "AI interpretation is temporarily unavailable due to a provider restriction. Please try again later."
    if _is_model_missing(error):
        return "AI interpretation unavailable: the configured AI model is not available on its provider. Check the PRO_MODEL / API key settings."
    if "QUOTA_EXCEEDED" in text or "429" in text or "rate limit" in text.lower() or "too many requests" in text.lower():
        delay = _retry_delay_seconds(error)
        if delay:
            return f"The AI provider is rate-limited (try again in ~{delay:.0f}s). Retrying with backups…"
        return "The AI provider is rate-limited. Retrying with backups…"
    if "permission_denied" in text.lower() or "401" in text:
        return "AI interpretation unavailable: provider authentication failed."
    if "timeout" in text.lower() or "timed out" in text.lower():
        return "AI interpretation timed out. Please try again."
    if len(text) > 180:
        return f"AI interpretation failed: {text[:180]}…"
    return f"AI interpretation failed: {text}"


async def interpret_stream(pipeline_type: str, context: dict) -> AsyncGenerator[str, None]:
    candidates = llm_client.get_all_candidates()
    if not candidates:
        yield _error_event("No LLM API keys configured. AI interpretation unavailable.")
        return

    prompt = llm_client.build_prompt(pipeline_type, context)
    last_error = None

    for candidate in candidates:
        # Per-provider retries with exponential backoff, honoring any
        # provider-returned retry-after delay (e.g. Gemini free-tier 429s).
        for attempt in range(3):
            try:
                response = await acompletion(
                    model=candidate["model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    stream=True,
                    timeout=25,
                    api_key=candidate["api_key"],
                )
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield _chunk_event(chunk.choices[0].delta.content)

                yield _done_event({"model": candidate["model"], "pipeline_type": pipeline_type})
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM provider %s attempt %d failed: %s",
                    candidate["name"],
                    attempt + 1,
                    e,
                )
                if _is_model_missing(e):
                    break
                delay = _retry_delay_seconds(e) or (2 ** attempt)
                if attempt < 2:
                    yield _retry_event(candidate["name"], attempt + 1, delay)
                    await asyncio.sleep(delay)

        yield _notice_event(f"Provider {candidate['name']} unavailable, trying next…")

    yield _error_event(_friendly_error(last_error) if last_error else "All AI providers failed.")


async def interpret_text(pipeline_type: str, context: dict) -> dict:
    """Non-streaming interpretation for pipeline runs — same retry/fallback logic."""
    candidates = llm_client.get_all_candidates()
    if not candidates:
        return {"interpretation": "AI interpretation unavailable: no LLM API keys configured"}

    prompt = llm_client.build_prompt(pipeline_type, context)
    last_error = None

    for candidate in candidates:
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    acompletion(
                        model=candidate["model"],
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=2000,
                        timeout=25,
                        api_key=candidate["api_key"],
                    ),
                    timeout=30,
                )
                text = response.choices[0].message.content if response.choices else ""
                if text:
                    return {"interpretation": text}
            except Exception as e:
                last_error = e
                logger.warning("LLM provider %s attempt %d failed: %s", candidate["name"], attempt + 1, e)
                if _is_model_missing(e):
                    break
                delay = _retry_delay_seconds(e) or (2 ** attempt)
                if attempt < 2:
                    await asyncio.sleep(delay)

    return {"interpretation": _friendly_error(last_error) if last_error else "All AI providers failed."}


def _chunk_event(text: str) -> str:
    return f"data: {json.dumps({'chunk': text})}\n\n"


def _done_event(meta: dict) -> str:
    return f"data: {json.dumps({'done': True, 'meta': meta})}\n\n"


def _error_event(msg: str) -> str:
    return f"data: {json.dumps({'error': msg})}\n\n"


def _retry_event(provider_name: str, attempt: int, delay: float) -> str:
    return f"data: {json.dumps({'notice': f'Retrying {provider_name} (attempt {attempt + 1}) in ~{delay:.0f}s…'})}\n\n"


def _notice_event(msg: str) -> str:
    return f"data: {json.dumps({'notice': msg})}\n\n"
