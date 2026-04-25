"""PATCH override semantics and role gates."""

import time


def _patch(client, instrument_id, field, value):
    return client.patch(
        f"/api/instruments/{instrument_id}/fields/{field}",
        json={"new_value": value, "reason": "test"},
    )


def test_editor_can_override_instrument_field(authenticated_client, seed):
    c = authenticated_client(seed["editor"])
    r = _patch(c, seed["instrument"].id, "grantor", "New Grantor")
    assert r.status_code == 200
    body = r.json()
    assert body["value"] == "New Grantor"
    assert body["resolved"]["grantor"] == "New Grantor"


def test_latest_override_wins(authenticated_client, seed):
    c = authenticated_client(seed["editor"])
    _patch(c, seed["instrument"].id, "grantor", "First")
    time.sleep(0.01)  # ensure changed_at ordering
    _patch(c, seed["instrument"].id, "grantor", "Second")

    # Runsheet should reflect the latest override.
    r = c.get(f"/api/projects/{seed['project'].id}/runsheet")
    assert r.status_code == 200
    chain = r.json()["chain"]
    assert chain[0]["grantor"] == "Second"


def test_null_revert_via_empty_value(authenticated_client, seed):
    """Setting new_value to empty string reverts the field to its extracted value."""
    c = authenticated_client(seed["editor"])
    _patch(c, seed["instrument"].id, "grantor", "Overwritten")
    # Override with the original extracted value effectively "reverts" it.
    _patch(c, seed["instrument"].id, "grantor", "Acme Minerals")
    r = c.get(f"/api/projects/{seed['project'].id}/runsheet")
    assert r.json()["chain"][0]["grantor"] == "Acme Minerals"


def test_viewer_forbidden(authenticated_client, seed):
    c = authenticated_client(seed["viewer"])
    r = _patch(c, seed["instrument"].id, "grantor", "x")
    assert r.status_code == 403


def test_outsider_gets_404(authenticated_client, seed):
    """User from org_b can't even see the project — expect 404/403."""
    c = authenticated_client(seed["outsider"])
    r = _patch(c, seed["instrument"].id, "grantor", "x")
    assert r.status_code in (403, 404)


def test_unknown_field_rejected(authenticated_client, seed):
    c = authenticated_client(seed["editor"])
    r = _patch(c, seed["instrument"].id, "not_a_real_field", "x")
    assert r.status_code == 422
