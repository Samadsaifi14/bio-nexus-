import logging
from fastapi import APIRouter, Request
from app.services.cache import get_cache_stats, reset_cache_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/cache-stats")
async def cache_stats():
    return get_cache_stats()


@router.post("/cache-stats/reset")
async def reset_stats():
    reset_cache_stats()
    return {"status": "ok"}
