import json
import logging
from typing import AsyncGenerator
from litellm import acompletion
from app.config import settings
from app.ai.llm_client import llm_client
from app.ai.prompts import get_prompt

logger = logging.getLogger(__name__)


async def interpret_stream(pipeline_type: str, context: dict) -> AsyncGenerator[str, None]:
    providers = llm_client.get_providers()
    if not providers:
        yield _error_event("No LLM API keys configured. AI interpretation unavailable.")
        return

    prompt = llm_client.build_prompt(pipeline_type, context)
    last_error = None

    for provider in providers:
        try:
            response = await acompletion(
                model=provider["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
                stream=True,
                timeout=25,
                api_key=provider["api_key"],
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield _chunk_event(chunk.choices[0].delta.content)

            yield _done_event({"model": provider["model"], "pipeline_type": pipeline_type})
            return
        except Exception as e:
            last_error = e
            logger.warning("LLM provider %s failed: %s", provider["name"], e)
            continue

    msg = str(last_error) if last_error else "All providers failed"
    if "organization_restricted" in msg or "Organization has been restricted" in msg:
        yield _error_event("AI interpretation is temporarily unavailable due to a provider restriction. Please try again later.")
    else:
        yield _error_event(f"AI interpretation failed: {msg}")


def _chunk_event(text: str) -> str:
    return f"data: {json.dumps({'chunk': text})}\n\n"


def _done_event(meta: dict) -> str:
    return f"data: {json.dumps({'done': True, 'meta': meta})}\n\n"


def _error_event(msg: str) -> str:
    return f"data: {json.dumps({'error': msg})}\n\n"
