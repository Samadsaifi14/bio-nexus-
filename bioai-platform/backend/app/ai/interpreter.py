import json
import os
from typing import AsyncGenerator
from litellm import acompletion
from app.config import settings
from app.ai.llm_client import llm_client
from app.ai.prompts import get_prompt


async def interpret_stream(pipeline_type: str, context: dict) -> AsyncGenerator[str, None]:
    if not llm_client.has_api_key():
        yield _error_event("GROQ_API_KEY is not configured. AI interpretation unavailable.")
        return

    prompt = llm_client.build_prompt(pipeline_type, context)
    model = llm_client.model

    try:
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
            stream=True,
            timeout=25,
            api_key=llm_client.api_key,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield _chunk_event(chunk.choices[0].delta.content)

        yield _done_event({"model": model, "pipeline_type": pipeline_type})
    except Exception as e:
        yield _error_event(str(e))


def _chunk_event(text: str) -> str:
    return f"data: {json.dumps({'chunk': text})}\n\n"


def _done_event(meta: dict) -> str:
    return f"data: {json.dumps({'done': True, 'meta': meta})}\n\n"


def _error_event(msg: str) -> str:
    return f"data: {json.dumps({'error': msg})}\n\n"
