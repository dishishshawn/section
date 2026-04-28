"""Stripe webhook: valid sig processes, bad sig → 400, stripe module mocked.

Coverage:
  - valid signature path
  - bad signature → 400
  - missing Stripe config → 501
  - idempotency: same event_id replays as no-op
  - metadata-less events fall back to customer_id lookup
  - customer.subscription.deleted flips billing_status to "canceled"
  - reconcile-seats endpoint is admin-gated
"""

import sys
import types


def _install_fake_stripe(monkeypatch, construct_event_returns=None, raises=None):
    """Register a fake `stripe` module so billing_routes can import it."""
    fake = types.ModuleType("stripe")

    class FakeWebhook:
        @staticmethod
        def construct_event(payload, sig, secret):
            if raises:
                raise raises
            return construct_event_returns

    fake.Webhook = FakeWebhook
    fake.api_key = None
    monkeypatch.setitem(sys.modules, "stripe", fake)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")


def test_webhook_valid_signature_updates_org(client, seed, monkeypatch, db):
    _install_fake_stripe(
        monkeypatch,
        construct_event_returns={
            "id": "evt_valid_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_ABC",
                    "status": "active",
                    "metadata": {"org_id": str(seed["org_a"].id)},
                }
            },
        },
    )
    r = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    assert r.status_code == 200
    assert r.json() == {"received": True}

    import models

    db.expire_all()
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    assert org.stripe_subscription_id == "sub_ABC"
    assert org.billing_status == "active"


def test_webhook_bad_signature_returns_400(client, monkeypatch):
    _install_fake_stripe(
        monkeypatch,
        raises=ValueError("Invalid signature"),
    )
    r = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_bad"},
        content=b"{}",
    )
    assert r.status_code == 400


def test_webhook_without_stripe_config_returns_501(client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig"},
        content=b"{}",
    )
    assert r.status_code == 501


# ---------------------------------------------------------------------------
# Task 9: idempotency, fallback, deletion, reconciliation
# ---------------------------------------------------------------------------


def test_duplicate_event_id_is_idempotent(client, seed, monkeypatch, db):
    """Posting the same event.id twice only applies side effects once."""
    _install_fake_stripe(
        monkeypatch,
        construct_event_returns={
            "id": "evt_dedupe_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_DEDUPE",
                    "status": "active",
                    "metadata": {"org_id": str(seed["org_a"].id)},
                }
            },
        },
    )
    r1 = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    assert r1.status_code == 200
    assert r1.json().get("duplicate") is not True

    # Mutate the org underneath so we can prove the 2nd delivery is a no-op.
    import models

    db.expire_all()
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    org.billing_status = "past_due"
    db.commit()

    r2 = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    assert r2.status_code == 200
    assert r2.json() == {"received": True, "duplicate": True}

    db.expire_all()
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    # Our local override survived → proves the duplicate did nothing.
    assert org.billing_status == "past_due"

    # Ledger contains exactly one row for this event_id.
    ledger = (
        db.query(models.StripeWebhookEvent)
        .filter_by(event_id="evt_dedupe_1")
        .all()
    )
    assert len(ledger) == 1


def test_missing_metadata_org_id_falls_back_to_customer(
    client, seed, monkeypatch, db
):
    """Events without metadata.org_id are still routed via customer_id."""
    import models

    # Pre-seed the org with a known Stripe customer id.
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    org.stripe_customer_id = "cus_FALLBACK_OK"
    db.commit()

    _install_fake_stripe(
        monkeypatch,
        construct_event_returns={
            "id": "evt_fallback_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_FB",
                    "status": "active",
                    "customer": "cus_FALLBACK_OK",
                    # NOTE: no metadata
                }
            },
        },
    )
    r = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    assert r.status_code == 200

    db.expire_all()
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    assert org.stripe_subscription_id == "sub_FB"
    assert org.billing_status == "active"


def test_subscription_deleted_updates_billing_status(
    client, seed, monkeypatch, db
):
    """customer.subscription.deleted flips org billing_status to 'canceled'."""
    import models

    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    org.stripe_customer_id = "cus_DELETED_OK"
    org.billing_status = "active"
    db.commit()

    _install_fake_stripe(
        monkeypatch,
        construct_event_returns={
            "id": "evt_deleted_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_GONE",
                    "status": "canceled",
                    "customer": "cus_DELETED_OK",
                }
            },
        },
    )
    r = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    assert r.status_code == 200

    db.expire_all()
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    assert org.billing_status == "canceled"


def test_reconcile_seats_admin_only(authenticated_client, seed):
    """viewer/member → 403, admin → 200 with current seat count."""
    org_id = seed["org_a"].id

    # viewer is a plain member → below 'admin' org role.
    viewer_client = authenticated_client(seed["viewer"])
    r = viewer_client.get(f"/api/billing/org/{org_id}/reconcile-seats")
    assert r.status_code == 403

    admin_client = authenticated_client(seed["admin"])
    r = admin_client.get(f"/api/billing/org/{org_id}/reconcile-seats")
    assert r.status_code == 200
    body = r.json()
    assert body["org_id"] == org_id
    # Four seeded members in org_a: owner/admin/editor/viewer.
    assert body["seat_count"] == 4
    # No STRIPE_SECRET_KEY configured in this test → not pushed.
    assert body["pushed_to_stripe"] is False


def test_concurrent_delivery_loses_unique_race(client, seed, monkeypatch, db):
    """Simulates the race window where two workers both pass the pre-check
    and race to INSERT. The loser hits the unique constraint, must roll back,
    and must NOT silently apply the side effect a second time.
    """
    import billing_routes
    import models

    _install_fake_stripe(
        monkeypatch,
        construct_event_returns={
            "id": "evt_race_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_LOSER",
                    "status": "past_due",
                    "metadata": {"org_id": str(seed["org_a"].id)},
                }
            },
        },
    )

    # Stage the race: a competing worker inserts the ledger row + applies its
    # own side effect AFTER our request passed the pre-check. We do that by
    # hooking into _resolve_org_from_event, which runs after the ledger row
    # has been queued in the session but before commit.
    real_resolve = billing_routes._resolve_org_from_event

    def competing_writer(db_, data):
        # Pretend a parallel worker already won: persist the ledger row and
        # the canonical side effect via a separate session on the same engine.
        other = type(db_)(bind=db_.bind)
        try:
            other.add(models.StripeWebhookEvent(
                event_id="evt_race_1",
                event_type="customer.subscription.updated",
                payload_hash="winner",
            ))
            org = other.query(models.Organization).filter_by(
                id=seed["org_a"].id
            ).first()
            org.stripe_subscription_id = "sub_WINNER"
            org.billing_status = "active"
            other.commit()
        finally:
            other.close()
        return real_resolve(db_, data)

    monkeypatch.setattr(billing_routes, "_resolve_org_from_event", competing_writer)

    r = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    # Loser sees IntegrityError on the ledger and reports duplicate.
    assert r.status_code == 200
    assert r.json() == {"received": True, "duplicate": True}

    db.expire_all()
    ledger = (
        db.query(models.StripeWebhookEvent)
        .filter_by(event_id="evt_race_1")
        .all()
    )
    # Exactly one ledger row — the winner's. The loser's was rolled back.
    assert len(ledger) == 1
    assert ledger[0].payload_hash == "winner"

    # Side effect reflects ONLY the winner; the loser did not overwrite it.
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    assert org.stripe_subscription_id == "sub_WINNER"
    assert org.billing_status == "active"


def test_side_effect_failure_rolls_back_ledger(client, seed, monkeypatch, db):
    """If side-effect commit fails, ledger row is rolled back so Stripe's
    retry can reprocess instead of being silently swallowed as a duplicate.
    """
    import billing_routes
    import models

    _install_fake_stripe(
        monkeypatch,
        construct_event_returns={
            "id": "evt_rollback_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_BOOM",
                    "status": "active",
                    "metadata": {"org_id": str(seed["org_a"].id)},
                }
            },
        },
    )

    # First delivery: force the side-effect path to explode after the ledger
    # row has been added to the session but before commit.
    calls = {"n": 0}

    real_resolve = billing_routes._resolve_org_from_event

    def boom(db_, data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated downstream failure")
        return real_resolve(db_, data)

    monkeypatch.setattr(billing_routes, "_resolve_org_from_event", boom)

    import pytest

    # TestClient re-raises unhandled server errors; that's fine for our
    # purposes — we only care that the DB state is consistent afterward.
    with pytest.raises(RuntimeError, match="simulated downstream failure"):
        client.post(
            "/api/billing/webhook",
            headers={"stripe-signature": "sig_ok"},
            content=b"{}",
        )

    db.expire_all()
    ledger = (
        db.query(models.StripeWebhookEvent)
        .filter_by(event_id="evt_rollback_1")
        .all()
    )
    # Atomic rollback: ledger insert undone alongside the failed side effect.
    assert len(ledger) == 0

    # Stripe retries the same event_id → processed cleanly this time.
    r2 = client.post(
        "/api/billing/webhook",
        headers={"stripe-signature": "sig_ok"},
        content=b"{}",
    )
    assert r2.status_code == 200
    assert r2.json() == {"received": True}

    db.expire_all()
    org = db.query(models.Organization).filter_by(id=seed["org_a"].id).first()
    assert org.stripe_subscription_id == "sub_BOOM"
    assert org.billing_status == "active"
    ledger = (
        db.query(models.StripeWebhookEvent)
        .filter_by(event_id="evt_rollback_1")
        .all()
    )
    assert len(ledger) == 1
