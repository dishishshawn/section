import os
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import (
    consume_code,
    get_current_user,
    is_email_allowed,
    issue_code,
    make_session_cookie,
    send_verification_code,
    SESSION_TTL_SECONDS,
    IS_PRODUCTION,
)
from database import get_db
from models import User
from rate_limit import client_ip, enforce_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "section_session"
_dev_mode = not os.getenv("RESEND_API_KEY")


class RequestCodeBody(BaseModel):
    email: EmailStr


class RequestCodeResponse(BaseModel):
    # Generic acknowledgement — never reveals whether the email is allowed,
    # to prevent enumeration. Dev mode echoes the code for local testing.
    sent: bool = True
    dev_code: str | None = None


class VerifyCodeBody(BaseModel):
    email: EmailStr
    code: str


class MeResponse(BaseModel):
    id: int
    email: str
    display_name: str | None

    model_config = {"from_attributes": True}


def _normalize_email(raw: str) -> str:
    return raw.strip().lower()


@router.post("/request-code", response_model=RequestCodeResponse)
def request_code(
    body: RequestCodeBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Email a 6-digit code to `email` if it belongs to a known user, an active
    invite, or the bootstrap allowlist. Always returns the same shape so a
    caller can't tell whether an address is on the allowlist.
    """
    email = _normalize_email(body.email)
    enforce_rate_limit(
        db,
        key=f"auth:request-code:ip:{client_ip(request)}",
        max_count=10,
        window_seconds=60,
        detail="Too many sign-in attempts from this network. Try again in a minute.",
    )
    enforce_rate_limit(
        db,
        key=f"auth:request-code:email:{email}",
        max_count=5,
        window_seconds=3600,
        detail="Too many sign-in codes requested for this email. Try again later.",
    )

    if not is_email_allowed(db, email):
        # Silently no-op on disallowed emails — same response shape, no code
        # generated, no email sent. Rate-limit counter still ticks above so
        # an attacker can't enumerate by timing or count.
        return RequestCodeResponse()

    code = issue_code(db, email)
    send_verification_code(email, code)
    if _dev_mode and not IS_PRODUCTION:
        return RequestCodeResponse(dev_code=code)
    return RequestCodeResponse()


@router.post("/verify-code", response_model=MeResponse)
def verify_code(
    body: VerifyCodeBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = _normalize_email(body.email)
    # Per-IP cap on verify too — defends the 10^6 space across multiple emails.
    enforce_rate_limit(
        db,
        key=f"auth:verify-code:ip:{client_ip(request)}",
        max_count=20,
        window_seconds=60,
        detail="Too many code attempts. Try again in a minute.",
    )
    consume_code(db, email, body.code)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Code consumed → email passed the allowlist gate at request time, so
        # this is the legitimate first sign-in for an invitee or bootstrap email.
        user = User(email=email, session_version=0)
        db.add(user)
        db.commit()
        db.refresh(user)

    cookie = make_session_cookie(user.id, user.session_version or 0)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=cookie,
        httponly=True,
        samesite="lax",
        secure=IS_PRODUCTION,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return user


@router.post("/signout", status_code=204)
def signout(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.session_version = (user.session_version or 0) + 1
    db.add(user)
    db.commit()
    response.delete_cookie(key=SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return user
