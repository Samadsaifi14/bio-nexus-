import base64
import json
import logging
from datetime import date

import httpx
from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_user_id(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        return claims.get("sub")
    except Exception:
        return None


async def check_daily_limit(request: Request) -> None:
    user_id = _extract_user_id(request)
    if not user_id:
        logger.info("Rate limit check skipped: no authenticated user session")
        return

    try:
        today = date.today().isoformat()
        url = (
            f"{settings.SUPABASE_URL}/rest/v1/jobs"
            f"?user_id=eq.{user_id}"
            f"&created_at=gte.{today}T00:00:00"
            f"&select=id"
        )
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Prefer": "count=exact",
        }
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        content_range = resp.headers.get("content-range", "*/0")
        total = int(content_range.split("/")[-1])

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check skipped (Supabase unreachable): {e}")
        return

    if total >= settings.DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_exceeded",
                "message": f"You've used all {settings.DAILY_LIMIT} daily analyses. Resets at midnight IST.",
                "used": total,
                "limit": settings.DAILY_LIMIT,
            },
        )
