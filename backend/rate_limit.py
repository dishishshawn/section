"""
Minimal SQLite-backed token-bucket rate limiter.

Design notes
------------
- Keyed by an arbitrary string (e.g. ``auth:request-link:email:alice@x.com`` or
  ``auth:request-link:ip:1.2.3.4``). Callers are responsible for composing keys.
- One row per (key, bucket_name). ``window_start`` + ``window_seconds`` defines
  the rolling window — when the window expires, the bucket resets on the next
  check. Simple, predictable, easy to test.
- State lives in the same DB as the rest of the app, so no extra process is
  required. Multi-instance deployments should swap this for Redis — the
  ``check_rate_limit`` signature is intentionally the only contract consumers
  rely on.
- FastAPI integration: ``enforce_rate_limit`` raises ``HTTPException(429)`` with
  a ``Retry-After`` header so browsers and tests see a conformant response.

This module is test-friendly: ``_now`` is a module-level function the tests can
monkeypatch to fast-forward the clock.
"""

from __future__ import annotations

import time
from typing import Tuple

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session


def _now() -> float:
    """Seconds since epoch. Indirection point so tests can freeze time."""
    return time.time()


def check_rate_limit(
    db: Session,
    key: str,
    max_count: int,
    window_seconds: int,
) -> Tuple[bool, int]:
    """
    Atomically increment the bucket for ``key`` and decide whether the caller
    is still under ``max_count`` in the current ``window_seconds`` window.

    Returns
    -------
    (allowed, retry_after_seconds)
        ``allowed`` is ``True`` when the request may proceed.
        ``retry_after_seconds`` is the number of seconds until the window
        resets (only meaningful when ``allowed`` is ``False``; ``0`` otherwise).

    The call is self-committing — callers should not need to wrap it in a
    transaction. We tolerate concurrent increments: at worst, a burst may
    allow a single extra request through, which is acceptable for anti-abuse
    limits on auth + invite endpoints.
    """
    now = _now()

    row = db.execute(
        text("SELECT count, window_start FROM rate_limit_buckets WHERE key = :k"),
        {"k": key},
    ).fetchone()

    if row is None:
        db.execute(
            text(
                "INSERT INTO rate_limit_buckets (key, count, window_start) "
                "VALUES (:k, 1, :w)"
            ),
            {"k": key, "w": now},
        )
        db.commit()
        return True, 0

    count, window_start = row[0], row[1]
    elapsed = now - window_start

    if elapsed >= window_seconds:
        # Window expired — reset to a fresh bucket starting at "now".
        db.execute(
            text(
                "UPDATE rate_limit_buckets "
                "SET count = 1, window_start = :w WHERE key = :k"
            ),
            {"k": key, "w": now},
        )
        db.commit()
        return True, 0

    if count >= max_count:
        retry_after = max(1, int(window_seconds - elapsed) + 1)
        return False, retry_after

    db.execute(
        text(
            "UPDATE rate_limit_buckets SET count = count + 1 WHERE key = :k"
        ),
        {"k": key},
    )
    db.commit()
    return True, 0


def peek_count(db: Session, key: str, window_seconds: int) -> int:
    """Read the current bucket count without mutating it.

    Returns 0 when the bucket is missing or its window has expired. Useful
    for soft-lock checks that should reject independently of incrementing
    the counter that drove the lock.
    """
    row = db.execute(
        text("SELECT count, window_start FROM rate_limit_buckets WHERE key = :k"),
        {"k": key},
    ).fetchone()
    if row is None:
        return 0
    count, window_start = row[0], row[1]
    if _now() - window_start >= window_seconds:
        return 0
    return int(count)


def record_event(db: Session, key: str, window_seconds: int) -> None:
    """Increment a bucket without enforcing any cap.

    For tracking signals (e.g. failed auth attempts) where the threshold is
    evaluated separately. Reuses ``check_rate_limit`` with an unreachable
    ``max_count`` so the bucket lifecycle (window resets, atomic increment)
    is shared with the enforcement path.
    """
    check_rate_limit(db, key, max_count=10**9, window_seconds=window_seconds)


def enforce_rate_limit(
    db: Session,
    key: str,
    max_count: int,
    window_seconds: int,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    """
    Convenience wrapper: check the bucket and raise HTTP 429 with a
    ``Retry-After`` header when the limit is exceeded.
    """
    allowed, retry_after = check_rate_limit(db, key, max_count, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


def client_ip(request: Request) -> str:
    """
    Best-effort client IP resolution. Honors ``X-Forwarded-For`` (first hop)
    when present so proxied deployments still get per-client buckets; falls
    back to the socket peer. Returns a stable string suitable for use in a
    rate-limit key.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # First entry is the original client. Trim whitespace defensively.
        return xff.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
