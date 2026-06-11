try:
    from celery import Celery
    from app.config import settings

    celery_app = Celery(
        "bio_nexus",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

    import redis
    r = redis.from_url(settings.REDIS_URL)
    r.ping()
    r.close()
except Exception:
    celery_app = None
