"""Structured JSON logging for the backend.

Stdlib-only JSON formatter — no extra deps required. Emits one JSON object per
log line with time, level, logger, message, plus any contextvars attached by
middleware (request_id, user_id, route).

Usage:
    from logging_config import setup_logging, get_logger, bind_user

    setup_logging()
    log = get_logger(__name__)
    log.info("something happened", extra={"foo": "bar"})
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Contextvars populated by RequestIDMiddleware / auth dependencies. These are
# read on every log record so emitted JSON always carries request correlation
# data when available.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "user_id", default=None
)
route_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "route", default=None
)


# Reserved LogRecord attrs we skip when serializing `extra` fields.
_RESERVED_RECORD_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter — no external deps."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "route": route_var.get(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Pull any structured extras attached via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key in payload:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str | None = None) -> None:
    """Install JSON formatter on the root logger. Idempotent."""
    lvl = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    root.setLevel(lvl)

    # Drop existing handlers so repeated calls (tests) don't duplicate output.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Keep uvicorn's access / error loggers in the JSON stream too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def bind_user(user_id: int | None) -> None:
    """Attach the current user's id to the log context for this request."""
    user_id_var.set(user_id)


def bind_request(request_id: str | None, route: str | None = None) -> None:
    request_id_var.set(request_id)
    route_var.set(route)
