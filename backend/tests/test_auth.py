"""Code-based auth: request-code → verify-code → /me round trip.

Also covers the email-allowlist gate (existing user, pending invite, or
AUTH_BOOTSTRAP_EMAILS) and the hardening properties of the code itself
(attempt cap, expiry, single-use)."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import models
from auth import CODE_MAX_ATTEMPTS, issue_code

# ---------------------------------------------------------------------------
# Allowlist gate
# ---------------------------------------------------------------------------


def test_request_code_unknown_email_silently_no_ops(client, db, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("AUTH_BOOTSTRAP_EMAILS", raising=False)
    r = client.post("/api/auth/request-code", json={"email": "stranger@example.com"})
    assert r.status_code == 200
    body = r.json()
    # Generic response — no dev_code echoed for disallowed emails, even in dev.
    assert body.get("dev_code") is None
    assert db.query(models.EmailVerificationCode).filter_by(email="stranger@example.com").count() == 0


def test_request_code_allowed_for_existing_user(client, db, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    db.add(models.User(email="known@example.com", session_version=0))
    db.commit()
    r = client.post("/api/auth/request-code", json={"email": "known@example.com"})
    assert r.status_code == 200
    assert r.json().get("dev_code"), "dev_code should be echoed in dev mode"


def test_request_code_allowed_for_pending_invite(client, db, seed, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    invite = models.OrgInvite(
        org_id=seed["org_a"].id,
        invited_email="newhire@example.com",
        role="member",
        token="t-newhire",
        invited_by=seed["owner"].id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(invite)
    db.commit()

    r = client.post("/api/auth/request-code", json={"email": "newhire@example.com"})
    assert r.json().get("dev_code")


def test_request_code_allowed_for_bootstrap_email(client, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("AUTH_BOOTSTRAP_EMAILS", "founder@example.com,co@example.com")
    r = client.post("/api/auth/request-code", json={"email": "founder@example.com"})
    assert r.json().get("dev_code")


# ---------------------------------------------------------------------------
# Verify code happy path + cookie
# ---------------------------------------------------------------------------


def test_verify_code_creates_user_and_sets_cookie(client, monkeypatch):
    monkeypatch.setenv("AUTH_BOOTSTRAP_EMAILS", "first@example.com")
    r = client.post("/api/auth/request-code", json={"email": "first@example.com"})
    code = r.json()["dev_code"]
    assert code

    r = client.post(
        "/api/auth/verify-code",
        json={"email": "first@example.com", "code": code},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "first@example.com"
    assert any(c.name == "section_session" for c in client.cookies.jar)

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "first@example.com"


def test_verify_code_rejects_wrong_code(client, db):
    db.add(models.User(email="someone@example.com", session_version=0))
    db.commit()
    issue_code(db, "someone@example.com")
    r = client.post(
        "/api/auth/verify-code",
        json={"email": "someone@example.com", "code": "000000"},
    )
    assert r.status_code == 400


def test_verify_code_locks_after_max_attempts(client, db):
    db.add(models.User(email="brute@example.com", session_version=0))
    db.commit()
    code = issue_code(db, "brute@example.com")
    for _ in range(CODE_MAX_ATTEMPTS):
        client.post(
            "/api/auth/verify-code",
            json={"email": "brute@example.com", "code": "999999"},
        )
    # Even the correct code is rejected once the row hits the attempt cap and
    # is purged. Attacker can't blow through 10^6 by retrying.
    r = client.post(
        "/api/auth/verify-code",
        json={"email": "brute@example.com", "code": code},
    )
    assert r.status_code == 400


def test_verify_code_rejects_expired(client, db):
    db.add(models.User(email="slowpoke@example.com", session_version=0))
    db.commit()
    code = issue_code(db, "slowpoke@example.com")
    row = db.query(models.EmailVerificationCode).filter_by(email="slowpoke@example.com").first()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    r = client.post(
        "/api/auth/verify-code",
        json={"email": "slowpoke@example.com", "code": code},
    )
    assert r.status_code == 400


def test_verify_code_is_single_use(client, db):
    db.add(models.User(email="oneshot@example.com", session_version=0))
    db.commit()
    code = issue_code(db, "oneshot@example.com")
    r1 = client.post(
        "/api/auth/verify-code",
        json={"email": "oneshot@example.com", "code": code},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/auth/verify-code",
        json={"email": "oneshot@example.com", "code": code},
    )
    assert r2.status_code == 400


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Email payload
# ---------------------------------------------------------------------------


def test_send_verification_code_email_payload(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("FROM_EMAIL", "noreply@section.app")
    monkeypatch.setenv("REPLY_TO_EMAIL", "no-reply@section.app")

    sent_payload = {}
    mock_resend = MagicMock()
    mock_resend.Emails.send.side_effect = lambda payload: sent_payload.update(payload)

    with patch.dict("sys.modules", {"resend": mock_resend}):
        from auth import send_verification_code

        send_verification_code("landman@section.app", "428193")

    assert "428193" in sent_payload.get("subject", "")
    assert "Section" in sent_payload.get("from", "")
    assert sent_payload.get("reply_to") == "no-reply@section.app"

    html = sent_payload.get("html", "")
    assert "<html" in html.lower()
    assert "428193" in html

    headers = sent_payload.get("headers", {})
    assert "List-Unsubscribe" in headers
    assert "List-Unsubscribe-Post" in headers


def test_verification_code_html_template():
    from email_templates import verification_code_html

    html = verification_code_html("428193", expiry_minutes=10)
    assert "428193" in html
    assert "10" in html
    assert "#4A5E3A" in html  # moss
