import hashlib
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.auth import require_user_id
from app.services.supabase import get_supabase

router = APIRouter()


class CreateKeyRequest(BaseModel):
    name: str


@router.get("")
async def list_api_keys(user_id: str = require_user_id):
    supabase = get_supabase()
    result = supabase.table("api_keys").select("id, name, key_prefix, created_at, last_used_at").eq("user_id", user_id).execute()
    return {"keys": result.data}


@router.post("")
async def create_api_key(req: CreateKeyRequest, user_id: str = require_user_id):
    raw = f"sk_bio_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:16]

    supabase = get_supabase()
    supabase.table("api_keys").insert({
        "user_id": user_id,
        "name": req.name,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
    }).execute()

    return {"key": raw, "key_prefix": key_prefix, "name": req.name}


@router.delete("/{key_id}")
async def delete_api_key(key_id: str, user_id: str = require_user_id):
    supabase = get_supabase()
    result = supabase.table("api_keys").select("id").eq("id", key_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")
    supabase.table("api_keys").delete().eq("id", key_id).execute()
    return {"status": "deleted"}
