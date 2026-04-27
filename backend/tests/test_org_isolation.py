"""Org-level isolation: user in org_a must not reach org_b projects."""

import models


def test_outsider_cannot_list_org_a_project(authenticated_client, seed):
    c = authenticated_client(seed["outsider"])
    r = c.get("/api/projects")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert seed["project"].id not in ids


def test_outsider_cannot_read_org_a_project(authenticated_client, seed):
    c = authenticated_client(seed["outsider"])
    r = c.get(f"/api/projects/{seed['project'].id}")
    assert r.status_code in (403, 404)


def test_outsider_cannot_export_org_a_project(authenticated_client, seed):
    c = authenticated_client(seed["outsider"])
    r = c.get(f"/api/projects/{seed['project'].id}/export/runsheet")
    assert r.status_code in (403, 404)


def test_outsider_search_does_not_leak_org_a(authenticated_client, seed):
    c = authenticated_client(seed["outsider"])
    r = c.get("/api/search", params={"q": "Test"})
    assert r.status_code == 200
    proj_ids = {p["id"] for p in r.json()["results"]["projects"]}
    assert seed["project"].id not in proj_ids


def test_viewer_in_org_a_can_read_but_not_edit(authenticated_client, seed):
    c = authenticated_client(seed["viewer"])
    r = c.get(f"/api/projects/{seed['project'].id}")
    assert r.status_code == 200
    # Edit attempts should 403
    r2 = c.patch(
        f"/api/instruments/{seed['instrument'].id}/fields/grantor",
        json={"new_value": "no", "reason": "x"},
    )
    assert r2.status_code == 403


def test_org_member_only_sees_own_org(authenticated_client, seed, db):
    # Create a project in org_b.
    other = models.Project(
        name="B Project",
        jurisdiction="OK",
        org_id=seed["org_b"].id,
        created_by=seed["outsider"].id,
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    c = authenticated_client(seed["owner"])
    r = c.get("/api/projects")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert other.id not in ids
    assert seed["project"].id in ids
