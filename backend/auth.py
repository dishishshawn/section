import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from database import get_db
from models import User

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
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


def make_session_cookie(user_id: int) -> str:
    return _session_serializer.dumps(user_id)


def _decode_session(token: str) -> int:
    try:
        return _session_serializer.loads(token, max_age=SESSION_TTL_SECONDS)
    except (SignatureExpired, BadSignature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — sign in again",
        )


def get_current_user(
    session: Optional[str] = Cookie(default=None, alias="section_session"),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    user_id = _decode_session(session)
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def send_magic_link(email: str, token: str) -> None:
    """Send magic link email. Falls back to stdout in dev if RESEND_API_KEY unset."""
    app_url = os.getenv("APP_URL", "http://localhost:8000")
    link = f"{app_url}/api/auth/verify?token={token}"

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print(f"\n[auth] Magic link for {email}:\n  {link}\n", flush=True)
        return

    import resend
    resend.api_key = api_key
    resend.Emails.send({
        "from": os.getenv("EMAIL_FROM", "Section <noreply@yourdomain.com>"),
        "to": email,
        "subject": "Sign in to Section",
        "html": (
            f"<p>Click to sign in to Section (link expires in 15 minutes):</p>"
            f'<p><a href="{link}">{link}</a></p>'
        ),
    })
