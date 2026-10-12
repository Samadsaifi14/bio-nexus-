import logging
import redis
import hashlib
import json
import functools
from typing import Callable, Any
from app.config import settings

logger = logging.getLogger(__name__)

_redis = None
_cache_stats = {"hits": 0, "misses": 0}


def init_redis():
    global _redis
    try:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis.ping()
        logger.info("Redis connected")
    except Exception:
        _redis = None
        logger.warning("Redis unavailable — caching disabled")


def get_redis():
    return _redis


def cache_get(key: str) -> str | None:
    r = get_redis()
    if r:
        val = r.get(key)
        if val is not None:
            _cache_stats["hits"] += 1
            return val
        _cache_stats["misses"] += 1
    return None


def cache_set(key: str, value: str, ttl: int = 86400):
    r = get_redis()
    if r:
        r.setex(key, ttl, value)


def get_cache_stats() -> dict:
    return {**_cache_stats, "redis_connected": _redis is not None}


def reset_cache_stats():
    _cache_stats["hits"] = 0
    _cache_stats["misses"] = 0


def ttl_cache(ttl: int = 86400, prefix: str = "cache"):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, input: dict, *args, **kwargs):
            raw = json.dumps(input, sort_keys=True)
            key_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
            cache_key = f"{prefix}:{key_hash}"

            cached = cache_get(cache_key)
            if cached is not None:
                try:
                    result = json.loads(cached)
                    if isinstance(result, dict):
                        result["from_cache"] = True
                    return result
                except (json.JSONDecodeError, TypeError):
                    pass

            result = await func(self, input, *args, **kwargs)
            try:
                cache_set(cache_key, json.dumps(result), ttl=ttl)
            except (TypeError, ValueError):
                pass
            if isinstance(result, dict):
                result["from_cache"] = False
            return result

        return wrapper

    return decorator
