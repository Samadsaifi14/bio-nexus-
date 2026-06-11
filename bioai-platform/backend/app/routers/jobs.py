from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from app.services.supabase import get_supabase

router = APIRouter()


@router.get("/count")
async def job_count(user_id: str = ""):
    supabase = get_supabase()
    today = datetime.now(timezone.utc).date().isoformat()
    result = supabase.table("jobs").select("id", count="exact").gte("created_at", today).execute()
    count = result.count or 0
    return {"count": count, "limit": 10, "remaining": max(0, 10 - count)}


@router.get("")
async def list_jobs(user_id: str = ""):
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").order("created_at", desc=True).limit(50).execute()
    return {"jobs": result.data or []}


@router.get("/{job_id}")
async def get_job(job_id: str):
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data[0]


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    supabase = get_supabase()
    supabase.table("jobs").delete().eq("id", job_id).execute()
    return {"status": "deleted"}
