"""
Rate-limit wiring tests.

These exercise the real enforce_rate_limit + route integration end-to-end
via FastAPI TestClient, not the helper in isolation — that way a future
refactor that bypasses the limiter on a live endpoint trips the test.
"""

from __future__ import annotations

from rate_limit import check_rate_limit


def test_request_code_email_bucket_trips_on_sixth(client, monkeypatch):
    """5 code requests for the same email succeed; the 6th returns 429.

    Email is on the bootstrap allowlist so each request actually issues a
    code (otherwise the silent no-op path would still consume the bucket
    but skip code creation — both are fine, but we want to assert against
    the success path here)."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("AUTH_BOOTSTRAP_EMAILS", "floodtarget@example.com")
    email = "floodtarget@example.com"

    for i in range(5):
        r = client.post("/api/auth/request-code", json={"email": email})
        assert r.status_code == 200, f"request {i + 1} should succeed, got {r.status_code}"

    r = client.post("/api/auth/request-code", json={"email": email})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert "email" in r.json()["detail"].lower() or "sign-in" in r.json()["detail"].lower()


def test_invite_org_bucket_trips_on_twentyfirst(client, authenticated_client, seed):
    """20 invites in the same org succeed; the 21st returns 429."""
    owner = seed["owner"]
    org_a = seed["org_a"]
    c = authenticated_client(owner)

    for i in range(20):
        r = c.post(
            f"/api/orgs/{org_a.id}/invites",
            json={"email": f"invitee{i}@example.com", "role": "member"},
        )
        assert r.status_code == 201, f"invite {i + 1} should succeed, got {r.status_code}: {r.text}"

    r = c.post(
        f"/api/orgs/{org_a.id}/invites",
        json={"email": "invitee-over@example.com", "role": "member"},
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_request_code_ip_hourly_blocks_email_rotation(client, monkeypatch):
    """One IP rotating through different allowlisted emails trips the
    hourly per-IP cap on /request-code (30/hour) before the per-email cap
    has a chance to fire on any one address."""
    import rate_limit

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    # Allowlist 31 distinct emails so per-email caps stay cold.
    emails = [f"rotator{i}@example.com" for i in range(31)]
    monkeypatch.setenv("AUTH_BOOTSTRAP_EMAILS", ",".join(emails))

    # Fake clock so the 10/min burst cap doesn't trip while we drive 30
    # requests against the 30/hour cap. Advance ~70s between requests:
    # fits inside the hourly window (3600s / 70 ≈ 51) but resets the burst.
    fake_clock = {"t": 1_000_000.0}
    monkeypatch.setattr(rate_limit, "_now", lambda: fake_clock["t"])

    for i, email in enumerate(emails[:30]):
        r = client.post("/api/auth/request-code", json={"email": email})
        assert r.status_code == 200, f"req {i + 1}: {r.status_code} {r.text}"
        fake_clock["t"] += 70

    r = client.post("/api/auth/request-code", json={"email": emails[30]})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert "network" in r.json()["detail"].lower()


def test_verify_failures_softlock_ip_across_emails(client, db, monkeypatch):
    """After AUTH_IP_FAIL_THRESHOLD bad verify attempts from one IP across
    different emails, both verify and request endpoints reject from that IP
    even when the per-email and short-window per-IP buckets are cold."""
    import auth_routes
    import models

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    threshold = auth_routes.AUTH_IP_FAIL_THRESHOLD

    # Issue real codes for `threshold` distinct emails so each bad-verify
    # attempt reaches consume_code (rather than being short-circuited by
    # "no code outstanding"). We feed wrong codes to drive the failure ticker.
    targets = [f"target{i}@example.com" for i in range(threshold)]
    monkeypatch.setenv("AUTH_BOOTSTRAP_EMAILS", ",".join(targets))
    for email in targets:
        from auth import issue_code

        issue_code(db, email)

    for email in targets:
        r = client.post(
            "/api/auth/verify-code",
            json={"email": email, "code": "000000"},
        )
        assert r.status_code == 400, f"want bad-code 400 for {email}"

    # Soft lock now fires on any further auth from this IP, even for a
    # brand-new email that has no per-email history.
    r = client.post(
        "/api/auth/request-code",
        json={"email": "fresh@example.com"},
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert "network" in r.json()["detail"].lower()

    r = client.post(
        "/api/auth/verify-code",
        json={"email": targets[0], "code": "000000"},
    )
    assert r.status_code == 429


def test_successful_verify_does_not_increment_fail_counter(client, db, monkeypatch):
    """A correct code on the first try must not tick the IP failure bucket
    (otherwise legitimate users would soft-lock themselves over time).
    """
    import auth_routes
    from auth import issue_code
    from rate_limit import peek_count

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("AUTH_BOOTSTRAP_EMAILS", "happy@example.com")

    code = issue_code(db, "happy@example.com")
    r = client.post(
        "/api/auth/verify-code",
        json={"email": "happy@example.com", "code": code},
    )
    assert r.status_code == 200, r.text

    # The IP failure bucket should be untouched (testserver is the request IP).
    fails = peek_count(
        db,
        key="auth:fail:ip:testclient",
        window_seconds=auth_routes.AUTH_IP_FAIL_WINDOW_SECONDS,
    )
    assert fails == 0


def test_different_keys_dont_share_bucket(db):
    """Two distinct keys each get their own counter — a hot key does not
    starve an unrelated one."""
    for _ in range(3):
        allowed, _ = check_rate_limit(db, "test:bucket:A", max_count=3, window_seconds=60)
        assert allowed
    blocked, retry_after = check_rate_limit(db, "test:bucket:A", max_count=3, window_seconds=60)
    assert not blocked
    assert retry_after > 0

    allowed, _ = check_rate_limit(db, "test:bucket:B", max_count=3, window_seconds=60)
    assert allowed
    allowed, _ = check_rate_limit(db, "test:bucket:B", max_count=3, window_seconds=60)
    assert allowed
