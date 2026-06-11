from fastapi import APIRouter, HTTPException
from app.services.supabase import get_supabase

router = APIRouter()


@router.get("/{token}")
async def get_shared_result(token: str):
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").eq("share_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Shared result not found")
    return result.data[0]
