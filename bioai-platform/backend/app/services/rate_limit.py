"""Rate limiting helpers.

- `check_daily_limit` counts today's jobs across all three tables.
- `check_daily_limit_pipelines`, `check_daily_limit_docking`, `check_daily_limit_sequencing`
  count per-table for tighter per-feature caps.
"""

import base64
import json
import logging
from datetime import date

import httpx
from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_user_id_from_request(request: Request) -> str | None:
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


async def _count_today_jobs(user_id: str, table: str) -> int:
    """Count today's jobs for a user in a specific table."""
    try:
        today = date.today().isoformat()
        url = (
            f"{settings.SUPABASE_URL}/rest/v1/{table}"
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
        return int(content_range.split("/")[-1])
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Daily count check skipped (table %s): %s", table, e)
        return 0


async def _enforce_limit(request: Request, table: str, limit: int, label: str) -> None:
    user_id = _extract_user_id_from_request(request)
    if not user_id:
        return

    total = await _count_today_jobs(user_id, table)
    if total >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_exceeded",
                "message": f"You've used all {limit} daily {label}. Resets at midnight UTC.",
                "used": total,
                "limit": limit,
            },
        )


async def check_daily_limit(request: Request) -> None:
    """Global daily limit across all tables (existing behavior)."""
    user_id = _extract_user_id_from_request(request)
    if not user_id:
        return

    tables = ["jobs", "docking_jobs", "sequencing_jobs"]
    total = 0
    for t in tables:
        total += await _count_today_jobs(user_id, t)

    if total >= settings.DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_exceeded",
                "message": f"You've used all {settings.DAILY_LIMIT} daily analyses. Resets at midnight UTC.",
                "used": total,
                "limit": settings.DAILY_LIMIT,
            },
        )


async def check_daily_limit_pipelines(request: Request) -> None:
    await _enforce_limit(request, "jobs", 10, "pipeline runs")


async def check_daily_limit_docking(request: Request) -> None:
    await _enforce_limit(request, "docking_jobs", 10, "docking jobs")


async def check_daily_limit_sequencing(request: Request) -> None:
    await _enforce_limit(request, "sequencing_jobs", 5, "sequencing jobs")
