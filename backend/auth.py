import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from database import get_db
from models import User

_DEV_SECRET = "dev-secret-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY") or ""
IS_PRODUCTION = os.getenv("ENV", "").lower() == "production"

if IS_PRODUCTION and (not SECRET_KEY or SECRET_KEY == _DEV_SECRET):
    raise RuntimeError(
        "SECRET_KEY must be set to a strong random value when ENV=production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
if not SECRET_KEY:
    SECRET_KEY = _DEV_SECRET

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="magic-link")
_session_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="session")

LINK_TTL_SECONDS = 15 * 60   # 15 min
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def make_magic_token(email: str) -> str:
    return _serializer.dumps(email)


def verify_magic_token(token: str) -> str:
    """Return email or raise HTTPException."""
    try:
        email = _serializer.loads(token, max_age=LINK_TTL_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Link expired — request a new one")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid link")
    return email


def make_session_cookie(user_id: int, session_version: int) -> str:
    """Serialize session as [user_id, session_version] so signout can revoke."""
    return _session_serializer.dumps([user_id, session_version])


def _decode_session(token: str) -> tuple[int, int]:
    try:
        payload = _session_serializer.loads(token, max_age=SESSION_TTL_SECONDS)
    except (SignatureExpired, BadSignature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — sign in again",
        )
    # Back-compat: older tokens were a bare int user_id (pre-revocation).
    if isinstance(payload, int):
        return payload, 0
    if isinstance(payload, (list, tuple)) and len(payload) == 2:
        return int(payload[0]), int(payload[1])
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Malformed session — sign in again",
    )


def get_current_user(
    session: Optional[str] = Cookie(default=None, alias="section_session"),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    user_id, session_version = _decode_session(session)
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    current_version = getattr(user, "session_version", 0) or 0
    if session_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked — sign in again",
        )
    return user


def send_magic_link(email: str, token: str) -> None:
    """Send magic link email. Falls back to stdout in dev if RESEND_API_KEY unset."""
    from email_templates import magic_link_html

    app_url = os.getenv("APP_URL", "http://localhost:8000")
    link = f"{app_url}/api/auth/verify?token={token}"

    from_address = os.getenv("FROM_EMAIL", "noreply@yourdomain.com")
    from_name = "Section"
    reply_to = os.getenv("REPLY_TO_EMAIL", f"no-reply@{from_address.split('@')[-1]}")

    html_body = magic_link_html(link, expiry_minutes=LINK_TTL_SECONDS // 60)

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print(f"\n[auth] Magic link for {email}:\n  {link}\n", flush=True)
        return

    import resend
    resend.api_key = api_key
    resend.Emails.send({
        "from": f"{from_name} <{from_address}>",
        "reply_to": reply_to,
        "to": email,
        "subject": "Sign in to Section",
        "html": html_body,
        "headers": {
            "List-Unsubscribe": f"<mailto:{reply_to}?subject=unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    })
