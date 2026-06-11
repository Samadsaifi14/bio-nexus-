import logging
from datetime import date

import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


async def check_daily_limit(user_id: str = "anonymous") -> None:
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
