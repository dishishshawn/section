"""
Organization, membership, invite, and project-sharing routes.

Role hierarchy (org level):  owner > admin > member
Role hierarchy (project level): owner > editor > viewer

All mutating endpoints require the caller to hold an org-level role of
at least 'admin' (or 'owner' for destructive operations).
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from rate_limit import client_ip, enforce_rate_limit
from permissions import (
    ORG_ROLE_RANK,
    PROJECT_ROLE_RANK,
    require_org_role,
    require_project_role,
)
from models import (
    OrgInvite,
    OrgMembership,
    Organization,
    Project,
    ProjectAccess,
    User,
)

router = APIRouter(prefix="/api/orgs", tags=["orgs"])

INVITE_TTL_HOURS = 72

# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------


def _org_membership(db: Session, user: User, org_id: int) -> OrgMembership | None:
    return db.query(OrgMembership).filter(OrgMembership.user_id == user.id, OrgMembership.org_id == org_id).first()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class OrgCreate(BaseModel):
    name: str
    slug: str


class OrgResponse(BaseModel):
    id: int
    name: str
    slug: str
    billing_status: str | None
    your_role: str | None = None

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: int
    email: str
    display_name: str | None
    role: str
    joined_at: str


class InviteBody(BaseModel):
    email: str
    role: str = "member"  # org-level role for new member
    project_id: int | None = None
    project_role: str | None = None


class InviteResponse(BaseModel):
    id: int
    invited_email: str
    role: str
    expires_at: str
    # dev-only: link is echoed when RESEND_API_KEY is unset
    dev_link: str | None = None


class ShareBody(BaseModel):
    user_id: int
    role: str  # owner | editor | viewer


class RoleUpdateBody(BaseModel):
    role: str


# ---------------------------------------------------------------------------
# Org CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=OrgResponse, status_code=201)
def create_org(
    body: OrgCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(Organization).filter(Organization.slug == body.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")
    org = Organization(name=body.name, slug=body.slug)
    db.add(org)
    db.flush()
    # Creator is automatically an owner
    m = OrgMembership(user_id=user.id, org_id=org.id, role="owner")
    db.add(m)
    db.commit()
    db.refresh(org)
    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        billing_status=org.billing_status,
        your_role="owner",
    )


@router.get("", response_model=list[OrgResponse])
def list_my_orgs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memberships = db.query(OrgMembership).filter(OrgMembership.user_id == user.id).all()
    result = []
    for m in memberships:
        org = m.org
        result.append(
            OrgResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                billing_status=org.billing_status,
                your_role=m.role,
            )
        )
    return result


@router.get("/{org_id}", response_model=OrgResponse)
def get_org(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = require_org_role(db, user, org_id, "member")
    org = m.org
    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        billing_status=org.billing_status,
        your_role=m.role,
    )


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{org_id}/members", response_model=list[MemberResponse])
def list_members(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "member")
    memberships = db.query(OrgMembership).filter(OrgMembership.org_id == org_id).all()
    return [
        MemberResponse(
            user_id=m.user_id,
            email=m.user.email,
            display_name=m.user.display_name,
            role=m.role,
            joined_at=m.joined_at.isoformat() if m.joined_at else "",
        )
        for m in memberships
    ]


@router.patch("/{org_id}/members/{target_user_id}", response_model=MemberResponse)
def update_member_role(
    org_id: int,
    target_user_id: int,
    body: RoleUpdateBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "owner")
    if body.role not in ORG_ROLE_RANK:
        raise HTTPException(status_code=422, detail="Invalid role")
    m = (
        db.query(OrgMembership)
        .filter(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == target_user_id,
        )
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    m.role = body.role
    db.commit()
    db.refresh(m)
    return MemberResponse(
        user_id=m.user_id,
        email=m.user.email,
        display_name=m.user.display_name,
        role=m.role,
        joined_at=m.joined_at.isoformat() if m.joined_at else "",
    )


@router.delete("/{org_id}/members/{target_user_id}", status_code=204)
def remove_member(
    org_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    caller_m = require_org_role(db, user, org_id, "admin")
    # Only owner can remove other owners
    target_m = (
        db.query(OrgMembership)
        .filter(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == target_user_id,
        )
        .first()
    )
    if not target_m:
        raise HTTPException(status_code=404, detail="Member not found")
    if target_m.role == "owner" and caller_m.role != "owner":
        raise HTTPException(status_code=403, detail="Only an owner can remove another owner")
    db.delete(target_m)
    db.commit()

    # Stripe: decrement seat count
    _stripe_adjust_seats(db, org_id)


# ---------------------------------------------------------------------------
# Invite flow
# ---------------------------------------------------------------------------


def _send_invite_email(invited_email: str, org_name: str, token: str, inviter_display: str) -> str:
    """Send invite email. Returns the link (always, for dev echo)."""
    app_url = os.getenv("APP_URL", "http://localhost:3000")
    link = f"{app_url}/invite/{token}"

    api_key = os.getenv("RESEND_API_KEY")
    if api_key:
        import html
        import resend  # type: ignore

        safe_inviter = html.escape(inviter_display or "Someone")
        safe_org = html.escape(org_name or "")
        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": os.getenv("EMAIL_FROM", "Section <noreply@yourdomain.com>"),
                "to": invited_email,
                "subject": f"{safe_inviter} invited you to {safe_org} on Section",
                "html": (
                    f"<p>{safe_inviter} has invited you to join <strong>{safe_org}</strong> on Section.</p>"
                    f'<p><a href="{link}">Accept invitation</a> (expires in {INVITE_TTL_HOURS} hours)</p>'
                ),
            }
        )
    else:
        print(
            f"\n[orgs] Invite link for {invited_email} → {org_name}:\n  {link}\n",
            flush=True,
        )
    return link


@router.post("/{org_id}/invites", response_model=InviteResponse, status_code=201)
def create_invite(
    org_id: int,
    body: InviteBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "admin")
    if body.role not in ORG_ROLE_RANK:
        raise HTTPException(status_code=422, detail="Invalid org role")

    # Anti-spam: 20 invites/day per org. Caps blast radius even if an admin
    # account is compromised or scripted.
    enforce_rate_limit(
        db,
        key=f"orgs:invite:org:{org_id}",
        max_count=20,
        window_seconds=86400,
        detail="This organization has reached its daily invite limit. Try again tomorrow.",
    )

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=INVITE_TTL_HOURS)

    invite = OrgInvite(
        org_id=org_id,
        invited_email=body.email.strip().lower(),
        role=body.role,
        project_id=body.project_id,
        project_role=body.project_role,
        token=token,
        invited_by=user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    dev_no_email = not os.getenv("RESEND_API_KEY")
    link = _send_invite_email(
        invite.invited_email,
        org.name,
        token,
        user.display_name or user.email,
    )

    return InviteResponse(
        id=invite.id,
        invited_email=invite.invited_email,
        role=invite.role,
        expires_at=invite.expires_at.isoformat(),
        dev_link=link if dev_no_email else None,
    )


@router.get("/invites/{token}")
def preview_invite(token: str, db: Session = Depends(get_db)):
    """Return invite metadata so the frontend can show a confirmation page."""
    invite = db.query(OrgInvite).filter(OrgInvite.token == token).first()
    if not invite or invite.accepted_at or datetime.utcnow() > invite.expires_at:
        raise HTTPException(status_code=404, detail="Invite not found or expired")
    org = db.query(Organization).filter(Organization.id == invite.org_id).first()
    return {
        "org_id": invite.org_id,
        "org_name": org.name if org else "",
        "invited_email": invite.invited_email,
        "role": invite.role,
    }


@router.post("/invites/{token}/accept", status_code=200)
def accept_invite(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Authenticated user accepts an invite. Their email must match.
    Creates OrgMembership (and optional ProjectAccess) then adjusts Stripe seats.
    """
    # Anti-abuse: brute-force guard on opaque invite tokens (token is 32 bytes
    # so brute force is already infeasible, but cap attempts anyway).
    enforce_rate_limit(
        db,
        key=f"orgs:invite-accept:ip:{client_ip(request)}",
        max_count=10,
        window_seconds=60,
        detail="Too many invite-accept attempts. Try again in a minute.",
    )
    invite = db.query(OrgInvite).filter(OrgInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at:
        raise HTTPException(status_code=409, detail="Invite already used")
    if datetime.utcnow() > invite.expires_at:
        raise HTTPException(status_code=410, detail="Invite expired")
    if invite.invited_email != user.email:
        raise HTTPException(status_code=403, detail="Invite is for a different email address")

    # Upsert org membership
    existing = _org_membership(db, user, invite.org_id)
    if not existing:
        m = OrgMembership(user_id=user.id, org_id=invite.org_id, role=invite.role)
        db.add(m)

    # Optional project access
    if invite.project_id and invite.project_role:
        pa = (
            db.query(ProjectAccess)
            .filter(
                ProjectAccess.user_id == user.id,
                ProjectAccess.project_id == invite.project_id,
            )
            .first()
        )
        if not pa:
            pa = ProjectAccess(
                user_id=user.id,
                project_id=invite.project_id,
                org_id=invite.org_id,
                role=invite.project_role,
                granted_by=invite.invited_by,
            )
            db.add(pa)

    invite.accepted_at = datetime.utcnow()
    db.commit()

    # Stripe: increment seat count
    _stripe_adjust_seats(db, invite.org_id)

    return {"status": "accepted", "org_id": invite.org_id}


# ---------------------------------------------------------------------------
# Project sharing (share menu)
# ---------------------------------------------------------------------------


@router.get("/{org_id}/projects/{project_id}/access")
def list_project_access(
    org_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "member")
    require_project_role(db, user, project_id, "viewer")
    accesses = (
        db.query(ProjectAccess)
        .filter(
            ProjectAccess.project_id == project_id,
            ProjectAccess.org_id == org_id,
        )
        .all()
    )
    return [
        {
            "user_id": a.user_id,
            "email": a.user.email,
            "display_name": a.user.display_name,
            "role": a.role,
        }
        for a in accesses
    ]


@router.post("/{org_id}/projects/{project_id}/access", status_code=201)
def grant_project_access(
    org_id: int,
    project_id: int,
    body: ShareBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "admin")
    require_project_role(db, user, project_id, "owner")
    if body.role not in PROJECT_ROLE_RANK:
        raise HTTPException(status_code=422, detail="Invalid project role")
    pa = (
        db.query(ProjectAccess)
        .filter(
            ProjectAccess.user_id == body.user_id,
            ProjectAccess.project_id == project_id,
        )
        .first()
    )
    if pa:
        pa.role = body.role
    else:
        pa = ProjectAccess(
            user_id=body.user_id,
            project_id=project_id,
            org_id=org_id,
            role=body.role,
            granted_by=user.id,
        )
        db.add(pa)
    db.commit()
    return {"status": "granted", "role": body.role}


@router.patch("/{org_id}/projects/{project_id}/access/{target_user_id}")
def update_project_access(
    org_id: int,
    project_id: int,
    target_user_id: int,
    body: RoleUpdateBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "admin")
    require_project_role(db, user, project_id, "owner")
    if body.role not in PROJECT_ROLE_RANK:
        raise HTTPException(status_code=422, detail="Invalid project role")
    pa = (
        db.query(ProjectAccess)
        .filter(
            ProjectAccess.user_id == target_user_id,
            ProjectAccess.project_id == project_id,
        )
        .first()
    )
    if not pa:
        raise HTTPException(status_code=404, detail="Access record not found")
    pa.role = body.role
    db.commit()
    return {"status": "updated", "role": body.role}


@router.delete("/{org_id}/projects/{project_id}/access/{target_user_id}", status_code=204)
def revoke_project_access(
    org_id: int,
    project_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_org_role(db, user, org_id, "admin")
    require_project_role(db, user, project_id, "owner")
    pa = (
        db.query(ProjectAccess)
        .filter(
            ProjectAccess.user_id == target_user_id,
            ProjectAccess.project_id == project_id,
        )
        .first()
    )
    if not pa:
        raise HTTPException(status_code=404, detail="Access record not found")
    db.delete(pa)
    db.commit()


# ---------------------------------------------------------------------------
# Stripe billing helpers
# ---------------------------------------------------------------------------


def _stripe_adjust_seats(db: Session, org_id: int):
    """
    Update the Stripe subscription quantity to match current member count.
    Silently skips if Stripe is not configured.
    """
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        return

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org or not org.stripe_subscription_id:
        return

    seat_count = db.query(OrgMembership).filter(OrgMembership.org_id == org_id).count()

    try:
        import stripe  # type: ignore

        stripe.api_key = stripe_key
        sub = stripe.Subscription.retrieve(org.stripe_subscription_id)
        item_id = sub["items"]["data"][0]["id"]
        stripe.SubscriptionItem.modify(item_id, quantity=seat_count)
    except Exception as exc:
        # Log but never crash a user-facing request on billing failure
        print(f"[stripe] failed to adjust seats for org {org_id}: {exc}", flush=True)
