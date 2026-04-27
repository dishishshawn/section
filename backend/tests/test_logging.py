"""Verify request ID middleware and JSON logging config.

Ensures:
  1. Every response echoes a UUID4 X-Request-ID header
  2. A client-supplied UUID is preserved (so upstream proxies can correlate)
  3. A non-UUID client value is ignored (we mint our own)
  4. JsonFormatter emits valid JSON with the expected keys
"""

from __future__ import annotations

import io
import json
import logging
import uuid

import pytest

from logging_config import (
    JsonFormatter,
    bind_request,
    get_logger,
    request_id_var,
    route_var,
    user_id_var,
)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def test_response_has_request_id_header(client):
    r = client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid is not None, "X-Request-ID response header is missing"
    assert _is_uuid(rid), f"X-Request-ID is not a UUID: {rid!r}"


def test_client_supplied_uuid_is_preserved(client):
    supplied = str(uuid.uuid4())
    r = client.get("/health", headers={"X-Request-ID": supplied})
    assert r.headers.get("X-Request-ID") == supplied


def test_non_uuid_request_id_is_replaced(client):
    r = client.get("/health", headers={"X-Request-ID": "not-a-uuid"})
    rid = r.headers.get("X-Request-ID")
    assert rid != "not-a-uuid"
    assert _is_uuid(rid)


def test_json_formatter_emits_json_with_context():
    # Bind context and emit a record through a temporary handler.
    bind_request("11111111-1111-1111-1111-111111111111", "/health")
    user_id_var.set(42)
    try:
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(JsonFormatter())
        lg = logging.getLogger("section.test.logging")
        lg.handlers = [handler]
        lg.setLevel(logging.INFO)
        lg.propagate = False

        lg.info("hello world", extra={"custom": "field"})

        line = buf.getvalue().strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["message"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["request_id"] == "11111111-1111-1111-1111-111111111111"
        assert payload["user_id"] == 42
        assert payload["route"] == "/health"
        assert payload["custom"] == "field"
        assert "time" in payload
    finally:
        # Clean up contextvars so we don't leak into other tests.
        request_id_var.set(None)
        route_var.set(None)
        user_id_var.set(None)


def test_sentry_noop_without_dsn(monkeypatch):
    """Sentry init is a safe no-op when SENTRY_DSN isn't set (the test env)."""
    import os

    assert not os.getenv("SENTRY_DSN"), "SENTRY_DSN must not be set in tests"
    # Reaching here without import errors means main.py imported cleanly
    # with the Sentry block skipped.
    import main  # noqa: F401
