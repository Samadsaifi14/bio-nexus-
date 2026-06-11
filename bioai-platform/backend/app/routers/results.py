from fastapi import APIRouter, HTTPException, Depends
from app.services.supabase import get_supabase
from app.ai.interpreter import interpret_stream
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/{job_id}")
async def get_result(job_id: str):
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data[0]


@router.get("/{job_id}/stream")
async def stream_result(job_id: str):
    supabase = get_supabase()
    job = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = job.data[0]
    context = job_data.get("context_json")
    pipeline_type = job_data.get("pipeline_type", "protein_analysis")

    if not context:
        raise HTTPException(status_code=400, detail="Job has not completed yet")

    return StreamingResponse(
        interpret_stream(pipeline_type, context),
        media_type="text/event-stream",
    )
