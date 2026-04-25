"""Smoke test the 3 PDF export endpoints."""

import pytest


@pytest.mark.parametrize("endpoint", [
    "/api/projects/{pid}/export/ownership",
    "/api/projects/{pid}/export/runsheet",
    "/api/projects/{pid}/export/stipulations",
])
def test_export_pdf_smoke(authenticated_client, seed, endpoint):
    c = authenticated_client(seed["owner"])
    r = c.get(endpoint.format(pid=seed["project"].id))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    body = r.content
    assert len(body) > 100
    # Reportlab always emits %PDF- as the leading magic bytes.
    assert body[:5] == b"%PDF-"


def test_title_opinion_pdf_smoke(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/projects/{seed['project'].id}/export/title-opinion")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"


def test_export_requires_access(authenticated_client, seed):
    c = authenticated_client(seed["outsider"])
    r = c.get(f"/api/projects/{seed['project'].id}/export/runsheet")
    assert r.status_code in (403, 404)
