import base64
import hashlib
import json
import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    """Extract Supabase user_id from the Bearer JWT, or None for anonymous users."""
    if credentials is None:
        return None
    try:
        parts = credentials.credentials.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        return claims.get("sub")
    except Exception:
        logger.debug("Failed to decode JWT", exc_info=True)
        return None


async def require_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Like get_user_id but raises 401 if no valid JWT is present."""
    uid = await get_user_id(credentials)
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return uid


async def get_user_id_from_api_key(request: Request) -> str | None:
    """Authenticate via X-API-Key header. Returns user_id or None."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    try:
        from app.services.supabase import get_supabase
        supabase = get_supabase()
        result = supabase.table("api_keys").select("user_id").eq("key_hash", key_hash).execute()
        if result.data:
            uid = result.data[0]["user_id"]
            supabase.table("api_keys").update({"last_used_at": "now()"}).eq("key_hash", key_hash).execute()
            return uid
    except Exception:
        pass
    return None


async def require_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,
) -> str:
    """Accepts either a Bearer JWT or X-API-Key header."""
    uid = await get_user_id(credentials)
    if uid:
        return uid
    uid = await get_user_id_from_api_key(request)
    if uid:
        return uid
    raise HTTPException(status_code=401, detail="Authentication required")
