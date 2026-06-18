import base64
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
