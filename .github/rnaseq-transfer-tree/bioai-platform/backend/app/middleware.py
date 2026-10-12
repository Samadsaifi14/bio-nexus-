"""Middleware that injects a request ID into every request and log context."""

from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import request_id_var, user_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request_id_var.set(rid)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000)

        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

        # Log the request
        import logging
        logger = logging.getLogger("access")
        logger.info(
            "%s %s %d %dms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
