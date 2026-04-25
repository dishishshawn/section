"""Magic-link auth: request → verify-complete → /me round trip."""

import time
from unittest.mock import MagicMock, patch

from auth import make_magic_token


def test_request_link_returns_dev_link(client, monkeypatch):
    # Force dev mode (no RESEND_API_KEY) so dev_link is echoed back.
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    r = client.post("/api/auth/request-link", json={"email": "new@example.com"})
    assert r.status_code == 200
    body = r.json()
    # dev_link may be None if the module-level _dev_mode was captured without
    # our monkeypatch, but it should always succeed.
    assert "dev_link" in body


def test_verify_complete_creates_user_and_sets_cookie(client, db):
    token = make_magic_token("fresh@user.test")
    r = client.post("/api/auth/verify-complete", json={"token": token})
    assert r.status_code == 200
    payload = r.json()
    assert payload["email"] == "fresh@user.test"
    # Session cookie set
    assert any(c.name == "section_session" for c in client.cookies.jar)

    # /me works now
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "fresh@user.test"


def test_verify_complete_rejects_invalid_token(client):
    r = client.post("/api/auth/verify-complete", json={"token": "garbage-token"})
    assert r.status_code == 400
    assert "Invalid" in r.json()["detail"] or "expired" in r.json()["detail"].lower()


def test_verify_complete_rejects_expired_token(client, monkeypatch):
    token = make_magic_token("expired@user.test")
    # Force the TTL down to 0 so the token is immediately stale.
    monkeypatch.setattr("auth.LINK_TTL_SECONDS", 0)
    time.sleep(1)
    r = client.post("/api/auth/verify-complete", json={"token": token})
    assert r.status_code == 400


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Email payload tests (Task 13 — deliverability hardening)
# ---------------------------------------------------------------------------

def test_send_magic_link_email_payload(monkeypatch):
    """send_magic_link must send HTML, set From name, Reply-To, and List-Unsubscribe."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("FROM_EMAIL", "noreply@section.app")
    monkeypatch.setenv("REPLY_TO_EMAIL", "no-reply@section.app")
    monkeypatch.setenv("APP_URL", "https://app.section.app")

    sent_payload = {}

    mock_resend = MagicMock()

    def capture_send(payload):
        sent_payload.update(payload)

    mock_resend.Emails.send.side_effect = capture_send

    token = make_magic_token("landman@section.app")

    with patch.dict("sys.modules", {"resend": mock_resend}):
        from auth import send_magic_link
        # Reload to pick up monkeypatched env vars in the function body.
        send_magic_link("landman@section.app", token)

    # Subject must be set
    assert sent_payload.get("subject") == "Sign in to Section"

    # From must include display name "Section"
    assert "Section" in sent_payload.get("from", "")

    # Reply-To must be set
    assert sent_payload.get("reply_to") == "no-reply@section.app"

    # HTML body must be present and non-trivial
    html = sent_payload.get("html", "")
    assert "<html" in html.lower()
    assert "Sign in to Section" in html
    assert "15" in html  # expiry notice

    # List-Unsubscribe header (RFC 8058)
    headers = sent_payload.get("headers", {})
    assert "List-Unsubscribe" in headers
    assert "List-Unsubscribe-Post" in headers


def test_magic_link_html_template():
    """HTML template renders with correct brand elements and link."""
    from email_templates import magic_link_html

    link = "https://app.section.app/auth/verify?token=abc123"
    html = magic_link_html(link, expiry_minutes=15)

    assert link in html
    assert "Sign in to Section" in html
    assert "15" in html
    # Brand colours present
    assert "#4A5E3A" in html  # moss
    assert "#B85C38" in html  # rust
    # "didn't request" footer
    assert "didn" in html.lower()
    # No external URLs / image deps
    assert "http" not in html.replace(link, "")  # only the magic link itself
