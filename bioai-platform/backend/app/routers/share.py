import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.auth import require_user_id
from app.services.supabase import get_supabase

router = APIRouter()


class ShareRequest(BaseModel):
    job_id: str


@router.get("/{token}")
async def get_shared_result(token: str):
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").eq("share_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Shared result not found")
    return result.data[0]


@router.post("")
async def create_share_link(req: ShareRequest, user_id: str = require_user_id):
    supabase = get_supabase()
    job = supabase.table("jobs").select("id, user_id, share_token").eq("id", req.job_id).execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your job")
    if job.data[0].get("share_token"):
        token = job.data[0]["share_token"]
    else:
        token = secrets.token_urlsafe(16)
        supabase.table("jobs").update({"share_token": token}).eq("id", req.job_id).execute()
    return {"token": token, "url": f"/shared/{token}"}
