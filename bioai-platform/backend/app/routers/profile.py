from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Optional
from app.services.supabase import get_supabase
from app.models.responses import ProfileUpdateResponse

router = APIRouter()

class ProfileUpdate(BaseModel):
    full_name: str = ""
    institution: str = ""

@router.get("")
async def get_profile(user_id: str = ""):
    supabase = get_supabase()
    result = supabase.table("profiles").select("*").limit(1).execute()
    if result.data:
        return result.data[0]
    return {"error": "Profile not found"}

@router.put("", response_model=ProfileUpdateResponse)
async def update_profile(profile: ProfileUpdate, user_id: str = ""):
    supabase = get_supabase()
    data = {}
    if profile.full_name: data["full_name"] = profile.full_name
    if profile.institution: data["institution"] = profile.institution
    if data:
        result = supabase.table("profiles").update(data).eq("id", user_id).execute()
        return {"status": "updated", "data": result.data[0] if result.data else data}
    return {"status": "no changes"}
