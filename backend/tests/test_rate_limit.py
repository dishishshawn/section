"""
Rate-limit wiring tests.

These exercise the real enforce_rate_limit + route integration end-to-end
via FastAPI TestClient, not the helper in isolation — that way a future
refactor that bypasses the limiter on a live endpoint trips the test.
"""

from __future__ import annotations

from rate_limit import check_rate_limit


def test_request_link_email_bucket_trips_on_sixth(client, monkeypatch):
    """5 magic-link requests for the same email succeed; the 6th returns 429."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    email = "floodtarget@example.com"

    for i in range(5):
        r = client.post("/api/auth/request-link", json={"email": email})
        assert r.status_code == 200, f"request {i + 1} should succeed, got {r.status_code}"

    r = client.post("/api/auth/request-link", json={"email": email})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    # Detail is human-readable, not a bare JSON-schema shape
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


def test_different_keys_dont_share_bucket(db):
    """Two distinct keys each get their own counter — a hot key does not
    starve an unrelated one."""
    # Fill key A up to its limit.
    for _ in range(3):
        allowed, _ = check_rate_limit(db, "test:bucket:A", max_count=3, window_seconds=60)
        assert allowed
    blocked, retry_after = check_rate_limit(db, "test:bucket:A", max_count=3, window_seconds=60)
    assert not blocked
    assert retry_after > 0

    # Key B is untouched and should still allow requests under the same limit.
    allowed, _ = check_rate_limit(db, "test:bucket:B", max_count=3, window_seconds=60)
    assert allowed
    allowed, _ = check_rate_limit(db, "test:bucket:B", max_count=3, window_seconds=60)
    assert allowed
