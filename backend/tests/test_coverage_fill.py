"""
Extra-coverage tests that exercise the read endpoints, overrides on all
entity types, org CRUD, and sharing — not about new logic, just about
lifting coverage above the 60% floor required by task 5.
"""

from datetime import datetime, timedelta

import models


def test_create_project_and_list(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.post(
        "/api/projects",
        json={"name": "New Proj", "jurisdiction": "OK", "org_id": seed["org_a"].id},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]

    r2 = c.get("/api/projects")
    assert any(p["id"] == new_id for p in r2.json())

    r3 = c.get(f"/api/projects/{new_id}")
    assert r3.status_code == 200


def test_project_read_endpoints(authenticated_client, seed):
    c = authenticated_client(seed["viewer"])
    pid = seed["project"].id
    for path in ("ownership", "obligations", "runsheet", "risk", "tract-map"):
        r = c.get(f"/api/projects/{pid}/{path}")
        assert r.status_code == 200, f"{path}: {r.text}"


def test_list_documents_empty(authenticated_client, seed):
    c = authenticated_client(seed["viewer"])
    r = c.get(f"/api/projects/{seed['project'].id}/documents")
    assert r.status_code == 200
    assert r.json() == []


def test_search_hits(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.get("/api/search", params={"q": "Test"})
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["results"]["projects"]}
    assert seed["project"].id in ids


def test_search_short_query_returns_empty(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.get("/api/search", params={"q": "a"})
    assert r.status_code == 200
    assert r.json()["results"]["projects"] == []


def test_delete_project_requires_owner(authenticated_client, seed, db):
    # Editor can't delete.
    ce = authenticated_client(seed["editor"])
    r = ce.delete(f"/api/projects/{seed['project'].id}")
    assert r.status_code == 403

    # Owner can.
    co = authenticated_client(seed["owner"])
    r2 = co.delete(f"/api/projects/{seed['project'].id}")
    assert r2.status_code == 200


def test_audit_log(authenticated_client, seed):
    c = authenticated_client(seed["editor"])
    c.patch(
        f"/api/instruments/{seed['instrument'].id}/fields/grantor",
        json={"new_value": "Audited", "reason": "QA"},
    )
    r = c.get(f"/api/projects/{seed['project'].id}/audit")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert any(e["field"] == "grantor" and e["new_value"] == "Audited" for e in entries)


def test_patch_interest_and_party(authenticated_client, seed):
    c = authenticated_client(seed["editor"])
    r1 = c.patch(
        f"/api/interests/{seed['interest'].id}/fields/mineral_estate",
        json={"new_value": "royalty"},
    )
    assert r1.status_code == 200

    r2 = c.patch(
        f"/api/parties/{seed['party'].id}/fields/name",
        json={"new_value": "Acme Corp"},
    )
    assert r2.status_code == 200


def test_patch_missing_instrument_returns_404(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.patch(
        "/api/instruments/999999/fields/grantor",
        json={"new_value": "x"},
    )
    assert r.status_code == 404


# ---------- org routes ----------


def test_create_and_list_org(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.post("/api/orgs", json={"name": "NewCo", "slug": "newco"})
    assert r.status_code == 201
    r2 = c.get("/api/orgs")
    assert any(o["slug"] == "newco" for o in r2.json())


def test_duplicate_org_slug_rejected(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    c.post("/api/orgs", json={"name": "Dup", "slug": "dup"})
    r = c.post("/api/orgs", json={"name": "Dup2", "slug": "dup"})
    assert r.status_code == 409


def test_list_members(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/orgs/{seed['org_a'].id}/members")
    assert r.status_code == 200
    emails = {m["email"] for m in r.json()}
    assert "owner@a.test" in emails


def test_non_member_cannot_read_org(authenticated_client, seed):
    c = authenticated_client(seed["outsider"])
    r = c.get(f"/api/orgs/{seed['org_a'].id}")
    assert r.status_code == 403


def test_get_billing_status(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/billing/org/{seed['org_a'].id}/status")
    assert r.status_code == 200
    assert r.json()["org_id"] == seed["org_a"].id


def test_checkout_requires_stripe_config(authenticated_client, seed, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    c = authenticated_client(seed["owner"])
    r = c.post("/api/billing/checkout", json={"org_id": seed["org_a"].id})
    assert r.status_code == 501


def test_share_project(authenticated_client, seed, db):
    # Owner shares the project with outsider (user in org_b).
    c = authenticated_client(seed["owner"])
    r = c.post(
        f"/api/orgs/{seed['org_a'].id}/projects/{seed['project'].id}/access",
        json={"user_id": seed["outsider"].id, "role": "viewer"},
    )
    assert r.status_code == 201

    r2 = c.get(f"/api/orgs/{seed['org_a'].id}/projects/{seed['project'].id}/access")
    assert r2.status_code == 200
    assert any(a["user_id"] == seed["outsider"].id for a in r2.json())

    # Update role
    r3 = c.patch(
        f"/api/orgs/{seed['org_a'].id}/projects/{seed['project'].id}/access/{seed['outsider'].id}",
        json={"role": "editor"},
    )
    assert r3.status_code == 200

    # Revoke
    r4 = c.delete(
        f"/api/orgs/{seed['org_a'].id}/projects/{seed['project'].id}/access/{seed['outsider'].id}"
    )
    assert r4.status_code == 204


def test_update_member_role(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.patch(
        f"/api/orgs/{seed['org_a'].id}/members/{seed['editor'].id}",
        json={"role": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_preview_expired_invite_404(client, seed, authenticated_client, db):
    body = authenticated_client(seed["owner"]).post(
        f"/api/orgs/{seed['org_a'].id}/invites",
        json={"email": "stale@a.test"},
    ).json()
    inv = db.query(models.OrgInvite).filter_by(id=body["id"]).first()
    inv.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    r = client.get(f"/api/orgs/invites/{inv.token}")
    assert r.status_code == 404
