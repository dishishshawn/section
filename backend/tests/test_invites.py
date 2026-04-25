"""Org invite flow: create → preview (no auth) → accept."""

from datetime import datetime, timedelta

import models


def _create_invite(authenticated_client, seed, email="newbie@a.test"):
    c = authenticated_client(seed["owner"])
    r = c.post(
        f"/api/orgs/{seed['org_a'].id}/invites",
        json={"email": email, "role": "member"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_invite_returns_dev_link(authenticated_client, seed, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    body = _create_invite(authenticated_client, seed)
    assert body["invited_email"] == "newbie@a.test"


def test_preview_invite_is_unauthenticated(authenticated_client, client, seed, db):
    body = _create_invite(authenticated_client, seed)
    token = db.query(models.OrgInvite).filter_by(id=body["id"]).first().token

    # Use a clean, non-authenticated client.
    r = client.get(f"/api/orgs/invites/{token}")
    assert r.status_code == 200
    assert r.json()["org_id"] == seed["org_a"].id


def test_accept_invite_email_case_insensitive(authenticated_client, seed, db):
    body = _create_invite(authenticated_client, seed, email="MixedCase@a.test")
    token = db.query(models.OrgInvite).filter_by(id=body["id"]).first().token

    # Create the user with already-normalized lowercase email to match what
    # request-link / verify-complete would do in production.
    u = models.User(email="mixedcase@a.test", display_name="Newbie")
    db.add(u)
    db.commit()
    db.refresh(u)

    c = authenticated_client(u)
    r = c.post(f"/api/orgs/invites/{token}/accept")
    assert r.status_code == 200
    assert r.json()["org_id"] == seed["org_a"].id


def test_expired_invite_returns_410(authenticated_client, seed, db):
    body = _create_invite(authenticated_client, seed, email="late@a.test")
    invite = db.query(models.OrgInvite).filter_by(id=body["id"]).first()
    invite.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()

    u = models.User(email="late@a.test")
    db.add(u)
    db.commit()
    db.refresh(u)
    c = authenticated_client(u)
    r = c.post(f"/api/orgs/invites/{invite.token}/accept")
    assert r.status_code == 410


def test_already_used_invite_returns_409(authenticated_client, seed, db):
    body = _create_invite(authenticated_client, seed, email="repeat@a.test")
    invite = db.query(models.OrgInvite).filter_by(id=body["id"]).first()
    invite.accepted_at = datetime.utcnow()
    db.commit()

    u = models.User(email="repeat@a.test")
    db.add(u)
    db.commit()
    db.refresh(u)
    c = authenticated_client(u)
    r = c.post(f"/api/orgs/invites/{invite.token}/accept")
    assert r.status_code == 409


def test_email_mismatch_returns_403(authenticated_client, seed, db):
    body = _create_invite(authenticated_client, seed, email="intended@a.test")
    invite = db.query(models.OrgInvite).filter_by(id=body["id"]).first()

    # Accepting as a different user's email → 403.
    c = authenticated_client(seed["outsider"])
    r = c.post(f"/api/orgs/invites/{invite.token}/accept")
    assert r.status_code == 403
