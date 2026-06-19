from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from app.services.supabase import get_supabase
from app.services.auth import get_user_id
from app.models.responses import JobCountResponse, JobDeleteResponse

router = APIRouter()


@router.get("/count", response_model=JobCountResponse)
async def job_count(user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    today = datetime.now(timezone.utc).date().isoformat()
    query = supabase.table("jobs").select("id", count="exact").gte("created_at", today)
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    count = result.count or 0
    return {"count": count, "limit": 10, "remaining": max(0, 10 - count)}


@router.get("")
async def list_jobs(user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    query = supabase.table("jobs").select("*").order("created_at", desc=True).limit(50)
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return {"jobs": result.data or []}


@router.get("/{job_id}")
async def get_job(job_id: str, user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    job = result.data[0]
    if user_id and job.get("user_id") and job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return job


@router.delete("/{job_id}", response_model=JobDeleteResponse)
async def delete_job(job_id: str, user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    result = supabase.table("jobs").select("id,user_id").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    job = result.data[0]
    if user_id and job.get("user_id") and job["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    supabase.table("jobs").delete().eq("id", job_id).execute()
    return {"status": "deleted"}
