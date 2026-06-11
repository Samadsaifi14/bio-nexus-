from datetime import date
from app.services.redis import get_redis
from app.config import settings


async def check_daily_limit(user_id: str = "anonymous") -> bool:
    r = get_redis()
    if not r:
        return True

    today = date.today().isoformat()
    key = f"rate_limit:daily:{user_id}:{today}"
    count = r.get(key)

    if count is None:
        r.setex(key, 86400, 1)
        return True

    if int(count) >= settings.DAILY_LIMIT:
        return False

    r.incr(key)
    return True


class RateLimitExceededError(Exception):
    pass
