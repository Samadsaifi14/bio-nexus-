import redis
import hashlib
import json
import functools
from typing import Callable, Any
from app.config import settings

_redis = None


def init_redis():
    global _redis
    try:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis.ping()
    except Exception:
        _redis = None


def get_redis():
    return _redis


def cache_get(key: str) -> str | None:
    r = get_redis()
    if r:
        return r.get(key)
    return None


def cache_set(key: str, value: str, ttl: int = 86400):
    r = get_redis()
    if r:
        r.setex(key, ttl, value)


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
                    return json.loads(cached)
                except (json.JSONDecodeError, TypeError):
                    pass

            result = await func(self, input, *args, **kwargs)
            try:
                cache_set(cache_key, json.dumps(result), ttl=ttl)
            except (TypeError, ValueError):
                pass
            return result

        return wrapper

    return decorator
