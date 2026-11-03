import hashlib
import logging
import os
import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# JWT verification
#
# Access tokens are *verified*, not merely decoded. The previous behaviour
# base64-decoded the payload and trusted whatever "sub" claim it found, so
# anyone could mint `header.payload.x` and impersonate any user id.
#
# Two verification paths, both failing closed:
# - SUPABASE_JWT_SECRET is set  -> local HS256 signature + exp check (PyJWT)
# - otherwise                   -> authoritative check against Supabase Auth
#                                    (GET /auth/v1/user), TTL-cached per token
# ---------------------------------------------------------------------------

_VERIFIED_TTL = 300  # seconds a network-verified token may be reused
_verified_cache: dict[str, tuple[str, float]] = {}  # sha256(token) -> (sub, expiry)


def _jwt_secret() -> str:
    return os.getenv("SUPABASE_JWT_SECRET", "")


def _verify_locally(token: str) -> str | None:
    """Verify HS256 signature and expiry against the Supabase JWT secret."""
    import jwt as pyjwt

    try:
        claims = pyjwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        return str(claims["sub"])
    except Exception:
        logger.debug("Local JWT verification failed", exc_info=True)
        return None


async def _verify_via_supabase(token: str) -> str | None:
    """Confirm the token is a live session via Supabase Auth (/auth/v1/user).

    Used when SUPABASE_JWT_SECRET is not configured. Network errors fail
    closed: an unverifiable token grants nothing.
    """
    import httpx

    from app.config import settings

    cache_key = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    cached = _verified_cache.get(cache_key)
    if cached and cached[1] > now:
        return cached[0]

    url = settings.SUPABASE_URL.rstrip("/") + "/auth/v1/user"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                },
            )
    except Exception:
        logger.warning(
            "Supabase auth verification unreachable; failing closed", exc_info=True
        )
        return None

    if resp.status_code != 200:
        return None
    try:
        sub = str(resp.json()["id"])
    except Exception:
        logger.debug("Malformed /auth/v1/user response", exc_info=True)
        return None

    if len(_verified_cache) > 10_000:
        _verified_cache.clear()
    _verified_cache[cache_key] = (sub, now + _VERIFIED_TTL)
    return sub


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2 and all(token.split("."))


async def get_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    """Extract the authenticated user_id from a Bearer JWT, else None."""
    if credentials is None:
        return None
    token = credentials.credentials
    if not _looks_like_jwt(token):
        return None

    if _jwt_secret():
        return _verify_locally(token)
    return await _verify_via_supabase(token)


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
