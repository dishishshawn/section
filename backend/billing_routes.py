"""
Stripe billing routes for per-seat pricing.

Environment variables required:
  STRIPE_SECRET_KEY        — Stripe secret key
  STRIPE_PRICE_ID          — Stripe Price ID for per-seat monthly plan
  STRIPE_WEBHOOK_SECRET    — Webhook signing secret (stripe listen --forward-to ...)
  APP_URL                  — Frontend base URL for redirect after checkout
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Organization, OrgMembership, User
from org_routes import _require_org_role

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


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe webhook events.
    Verify signature, then update org billing_status and stripe_subscription_id.
    """
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not stripe_key or not webhook_secret:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    payload = await request.body()

    try:
        import stripe  # type: ignore

        stripe.api_key = stripe_key
        event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook error: {exc}")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        org_id = data.get("metadata", {}).get("org_id")
        if org_id:
            org = db.query(Organization).filter(Organization.id == int(org_id)).first()
            if org:
                org.stripe_subscription_id = data["id"]
                org.billing_status = data["status"]
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
