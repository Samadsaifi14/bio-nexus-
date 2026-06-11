import json
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ai.interpreter import interpret_stream
from app.ai.llm_client import llm_client
from app.services.rate_limit import check_daily_limit

router = APIRouter()


class InterpretRequest(BaseModel):
    pipeline_type: str = "protein_analysis"
    context: dict = {}


@router.post("/interpret", dependencies=[Depends(check_daily_limit)])
async def interpret_full_context(req: InterpretRequest):
    if not llm_client.has_api_key():
        raise HTTPException(status_code=502, detail="GROQ_API_KEY is not configured")

    prompt = llm_client.build_prompt(req.pipeline_type, req.context)
    return {"prompt": prompt, "context_size": len(json.dumps(req.context))}


@router.post("/interpret/stream", dependencies=[Depends(check_daily_limit)])
async def interpret_stream_endpoint(req: InterpretRequest):
    return StreamingResponse(
        interpret_stream(req.pipeline_type, req.context),
        media_type="text/event-stream",
    )
