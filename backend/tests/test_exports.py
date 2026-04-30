"""Smoke test the 3 PDF export endpoints."""

import pytest


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/projects/{pid}/export/ownership",
        "/api/projects/{pid}/export/runsheet",
        "/api/projects/{pid}/export/stipulations",
    ],
)
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


# ---------------------------------------------------------------------------
# Burdens humanizer — turns the str()-of-dict that routes.py stores back into
# something readable in the PDF cells.
# ---------------------------------------------------------------------------


def test_humanize_burdens_dict_repr_string():
    from exports import _humanize_burdens

    assert _humanize_burdens("{'royalty_to_lessee': '1/4'}") == "Royalty to lessee: 1/4"


def test_humanize_burdens_real_dict():
    from exports import _humanize_burdens

    result = _humanize_burdens({"orri": "1/8 ORRI held by Smith", "royalty": "3/16"})
    assert "Orri: 1/8 ORRI held by Smith" in result
    assert "Royalty: 3/16" in result


def test_humanize_burdens_empty_or_none():
    from exports import _humanize_burdens

    assert _humanize_burdens(None) == "—"
    assert _humanize_burdens("") == "—"
    assert _humanize_burdens("None") == "—"


def test_humanize_burdens_non_literal_string_passthrough():
    """A free-text override (e.g. set via the override UI) shouldn't be parsed."""
    from exports import _humanize_burdens

    assert _humanize_burdens("Title defect — verify heirship") == "Title defect — verify heirship"


def test_humanize_burdens_list():
    from exports import _humanize_burdens

    assert "1/8 to Smith" in _humanize_burdens(["1/8 to Smith", "1/16 to Jones"])
    assert "1/16 to Jones" in _humanize_burdens(["1/8 to Smith", "1/16 to Jones"])


# ---------------------------------------------------------------------------
# Obligation priority bucketing — overdue items must not collapse into
# "high" / Within-30-days.
# ---------------------------------------------------------------------------


def test_obligations_overdue_branch(authenticated_client, seed, db):
    """An obligation 4000 days past due should be classified 'overdue', not 'high'."""
    import models
    from datetime import datetime, timedelta

    inst = seed["instrument"]
    db.add(
        models.Obligation(
            project_id=seed["project"].id,
            instrument_id=inst.id,
            type="primary_term_expiration",
            due_date=datetime.utcnow() - timedelta(days=4000),
            params={"description": "Lease expired ages ago"},
        )
    )
    # And a still-pending one for the same project so the buckets diversify.
    db.add(
        models.Obligation(
            project_id=seed["project"].id,
            instrument_id=inst.id,
            type="primary_term_expiration",
            due_date=datetime.utcnow() + timedelta(days=15),
            params={"description": "Coming up soon"},
        )
    )
    db.commit()

    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/projects/{seed['project'].id}/obligations")
    assert r.status_code == 200
    items = r.json()["obligations"]
    priorities = {o["priority"] for o in items}
    assert "overdue" in priorities
    assert "high" in priorities
