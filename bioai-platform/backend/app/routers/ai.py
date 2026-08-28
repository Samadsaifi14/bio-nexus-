import json
import logging
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ai.interpreter import interpret_stream
from app.ai.llm_client import llm_client
from app.services.rate_limit import check_daily_limit
from app.models.responses import InterpretResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class InterpretRequest(BaseModel):
    pipeline_type: str = "protein_analysis"
    context: dict = {}


class ToolInterpretRequest(BaseModel):
    """A single tool's result dict, interpreted on demand in plain language."""
    tool_name: str
    result: dict = {}


@router.post("/interpret", response_model=InterpretResponse)
async def interpret_full_context(req: InterpretRequest):
    if not llm_client.has_api_key():
        raise HTTPException(status_code=502, detail="GROQ_API_KEY is not configured")

    prompt = llm_client.build_prompt(req.pipeline_type, req.context)
    return {"prompt": prompt, "context_size": len(json.dumps(req.context))}


@router.post("/interpret/stream")
async def interpret_stream_endpoint(req: InterpretRequest):
    return StreamingResponse(
        interpret_stream(req.pipeline_type, req.context),
        media_type="text/event-stream",
    )


@router.post("/tool-interpret")
async def tool_interpret_endpoint(req: ToolInterpretRequest):
    """Generate a plain-language AI interpretation of a single tool result on demand."""
    from app.ai.tool_interpreter import interpret_tool_result

    interpretation = await interpret_tool_result(req.tool_name, req.result or {})
    if interpretation is None:
        message = "AI interpretation unavailable. Check that an LLM API key is configured, or try again later."
        logger.warning("tool-interpret returned no interpretation for '%s'", req.tool_name)
        raise HTTPException(status_code=422, detail=message)
    return interpretation
