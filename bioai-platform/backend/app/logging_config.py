"""Structured logging setup.

In production (ENVIRONMENT=prod), logs are emitted as JSON for easy parsing
by log aggregators. In development, human-readable format is used.

Every log line includes: timestamp, level, logger, message, and optional
request_id / user_id context injected by the middleware.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

_environment = os.getenv("ENVIRONMENT", "development")


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get("")
        if rid:
            log["request_id"] = rid
        uid = user_id_var.get("")
        if uid:
            log["user_id"] = uid
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable format for local development."""
    FMT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get("")
        uid = user_id_var.get("")
        prefix = ""
        if rid:
            prefix += f"[{rid[:8]}] "
        if uid:
            prefix += f"(user:{uid[:8]}) "
        record.msg = prefix + record.getMessage()
        return super().format(record)


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if _environment in ("production", "prod", "staging"):
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(DevFormatter())

    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("supabase").setLevel(logging.WARNING)
    logging.getLogger("postgrest").setLevel(logging.WARNING)
