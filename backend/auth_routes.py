import os
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    make_magic_token,
    make_session_cookie,
    send_magic_link,
    verify_magic_token,
    SESSION_TTL_SECONDS,
    IS_PRODUCTION,
)
from database import get_db
from models import User
from rate_limit import client_ip, enforce_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "section_session"
_dev_mode = not os.getenv("RESEND_API_KEY")
APP_URL = os.getenv("APP_URL", "http://localhost:3000").rstrip("/")


class RequestLinkBody(BaseModel):
    email: EmailStr


class RequestLinkResponse(BaseModel):
    dev_link: str | None = None


class VerifyCompleteBody(BaseModel):
    token: str


class MeResponse(BaseModel):
    id: int
    email: str
    display_name: str | None

    model_config = {"from_attributes": True}


def _normalize_email(raw: str) -> str:
    return raw.strip().lower()


@router.post("/request-link", response_model=RequestLinkResponse)
def request_link(
    body: RequestLinkBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Generate a magic link for the email and send it. Intentionally does NOT
    create a User row here — account creation happens on /verify-complete
    so anonymous POSTs can't fill the users table.
    """
    email = _normalize_email(body.email)
    # Anti-abuse: cap per-email (mailbox flooding / Resend bill) and per-IP
    # (enumeration sweeps). Enforce IP first so a single noisy client can't
    # prime N email buckets before being blocked.
    enforce_rate_limit(
        db,
        key=f"auth:request-link:ip:{client_ip(request)}",
        max_count=10,
        window_seconds=60,
        detail="Too many sign-in attempts from this network. Try again in a minute.",
    )
    enforce_rate_limit(
        db,
        key=f"auth:request-link:email:{email}",
        max_count=5,
        window_seconds=3600,
        detail="Too many sign-in links requested for this email. Try again later.",
    )
    token = make_magic_token(email)
    send_magic_link(email, token)
    if _dev_mode and not IS_PRODUCTION:
        return {"dev_link": f"{APP_URL}/auth/verify?token={token}"}
    return {}


@router.get("/verify")
def verify_redirect(token: str):
    """
    GET is non-mutating: it merely redirects the browser to the frontend
    verification page. The frontend then POSTs to /verify-complete to
    actually exchange the token for a session. This prevents email link
    preview bots and antivirus scanners from burning tokens.
    """
    return RedirectResponse(
        url=f"{APP_URL}/auth/verify?token={token}",
        status_code=303,
    )


@router.post("/verify-complete", response_model=MeResponse)
def verify_complete(body: VerifyCompleteBody, response: Response, db: Session = Depends(get_db)):
    email = _normalize_email(verify_magic_token(body.token))
    user = db.query(User).filter(User.email == email).first()
    if not user:
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
    # Bump the user's session_version so every outstanding token is invalidated.
    user.session_version = (user.session_version or 0) + 1
    db.add(user)
    db.commit()
    response.delete_cookie(key=SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return user
