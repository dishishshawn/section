"""
Stripe billing routes for per-seat pricing.

Environment variables required:
  STRIPE_SECRET_KEY        — Stripe secret key
  STRIPE_PRICE_ID          — Stripe Price ID for per-seat monthly plan
  STRIPE_WEBHOOK_SECRET    — Webhook signing secret (stripe listen --forward-to ...)
  APP_URL                  — Frontend base URL for redirect after checkout
"""

import hashlib
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Organization, OrgMembership, StripeWebhookEvent, User
from permissions import require_org_role as _require_org_role

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    org_id: int


@router.post("/checkout")
def create_checkout_session(
    body: CheckoutBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Creates a Stripe Checkout session for per-seat billing.
    Caller must be org owner.
    """
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    price_id = os.getenv("STRIPE_PRICE_ID")
    if not stripe_key or not price_id:
        raise HTTPException(
            status_code=501,
            detail="Stripe is not configured on this server",
        )

    _require_org_role(db, user, body.org_id, "owner")
    org = db.query(Organization).filter(Organization.id == body.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")

    seat_count = (
        db.query(OrgMembership)
        .filter(OrgMembership.org_id == body.org_id)
        .count()
    )

    try:
        import stripe  # type: ignore

        stripe.api_key = stripe_key
        app_url = os.getenv("APP_URL", "http://localhost:3000")

        # Create or reuse Stripe customer
        if not org.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"org_id": org.id, "org_slug": org.slug},
            )
            org.stripe_customer_id = customer["id"]
            db.commit()

        session = stripe.checkout.Session.create(
            customer=org.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": max(seat_count, 1),
                    "adjustable_quantity": {"enabled": False},
                }
            ],
            mode="subscription",
            subscription_data={
                "metadata": {"org_id": str(org.id)},
            },
            success_url=f"{app_url}/?billing=success&org={org.id}",
            cancel_url=f"{app_url}/?billing=canceled&org={org.id}",
        )
        return {"checkout_url": session["url"]}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stripe error: {exc}")


def _resolve_org_from_event(db: Session, data: dict) -> Organization | None:
    """Resolve target org from a Stripe event object.

    Prefer metadata.org_id; fall back to looking up by stripe_customer_id when
    metadata is missing (Stripe does not always echo metadata on every event).
    """
    metadata = data.get("metadata") or {}
    org_id = metadata.get("org_id")
    if org_id:
        try:
            return (
                db.query(Organization)
                .filter(Organization.id == int(org_id))
                .first()
            )
        except (TypeError, ValueError):
            pass

    customer_id = data.get("customer")
    if customer_id:
        return (
            db.query(Organization)
            .filter(Organization.stripe_customer_id == customer_id)
            .first()
        )
    return None


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    Hardened:
      - verify signature
      - idempotency: dedupe via stripe_webhook_events.event_id
      - fallback: when metadata.org_id is missing, find org via customer id
      - handle customer.subscription.deleted → billing_status = "canceled"
    """
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not stripe_key or not webhook_secret:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    payload = await request.body()

    try:
        import stripe  # type: ignore

        stripe.api_key = stripe_key
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook error: {exc}")

    event_id = event.get("id")
    event_type = event["type"]
    data = event["data"]["object"]

    # --- Idempotency: dedupe by event_id -----------------------------------
    if event_id:
        existing = (
            db.query(StripeWebhookEvent)
            .filter(StripeWebhookEvent.event_id == event_id)
            .first()
        )
        if existing:
            return {"received": True, "duplicate": True}

        # Insert BEFORE processing so a concurrent retry cannot reprocess.
        payload_hash = hashlib.sha256(payload or b"").hexdigest()
        ledger = StripeWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
        )
        db.add(ledger)
        try:
            db.commit()
        except IntegrityError:
            # Race: another worker inserted the same event_id concurrently.
            db.rollback()
            return {"received": True, "duplicate": True}

    # --- Dispatch ---------------------------------------------------------
    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        org = _resolve_org_from_event(db, data)
        if org:
            org.stripe_subscription_id = data.get("id")
            org.billing_status = data.get("status")
            # Backfill customer id if we learned it from this event.
            if not org.stripe_customer_id and data.get("customer"):
                org.stripe_customer_id = data["customer"]
            db.commit()

    elif event_type == "customer.subscription.deleted":
        org = _resolve_org_from_event(db, data)
        if org:
            org.stripe_subscription_id = None
            org.billing_status = "canceled"
            db.commit()

    return {"received": True}


@router.get("/org/{org_id}/status")
def get_billing_status(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_org_role(db, user, org_id, "member")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    seat_count = (
        db.query(OrgMembership).filter(OrgMembership.org_id == org_id).count()
    )
    return {
        "org_id": org_id,
        "billing_status": org.billing_status,
        "seat_count": seat_count,
        "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
    }


@router.get("/org/{org_id}/reconcile-seats")
def reconcile_seats(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Admin-only: recount members and push the quantity to Stripe.

    Useful after manual DB edits, failed webhook deliveries, or billing drift.
    """
    _require_org_role(db, user, org_id, "admin")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")

    seat_count = (
        db.query(OrgMembership).filter(OrgMembership.org_id == org_id).count()
    )

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    pushed = False
    error: str | None = None
    if stripe_key and org.stripe_subscription_id:
        try:
            import stripe  # type: ignore

            stripe.api_key = stripe_key
            sub = stripe.Subscription.retrieve(org.stripe_subscription_id)
            item_id = sub["items"]["data"][0]["id"]
            stripe.SubscriptionItem.modify(item_id, quantity=seat_count)
            pushed = True
        except Exception as exc:  # pragma: no cover - defensive
            error = str(exc)

    return {
        "org_id": org_id,
        "seat_count": seat_count,
        "pushed_to_stripe": pushed,
        "error": error,
    }
