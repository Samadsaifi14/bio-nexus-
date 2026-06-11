import redis
from app.config import settings

_r = None


def get_redis():
    global _r
    if _r is None:
        try:
            _r = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _r.ping()
        except Exception:
            _r = None
    return _r
