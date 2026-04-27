import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from database import get_db
from models import EmailVerificationCode, OrgInvite, User

_DEV_SECRET = "dev-secret-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY") or ""
IS_PRODUCTION = os.getenv("ENV", "").lower() == "production"

if IS_PRODUCTION and (not SECRET_KEY or SECRET_KEY == _DEV_SECRET):
    raise RuntimeError(
        "SECRET_KEY must be set to a strong random value when ENV=production. "
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
    )
if not SECRET_KEY:
    SECRET_KEY = _DEV_SECRET

_session_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="session")

CODE_TTL_SECONDS = 10 * 60  # 10 min
CODE_MAX_ATTEMPTS = 5
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def _bootstrap_emails() -> set[str]:
    """Emails permitted to sign in even without a User row or pending invite.

    Used to seed the very first org owners. Configure via comma-separated
    AUTH_BOOTSTRAP_EMAILS env var.
    """
    raw = os.getenv("AUTH_BOOTSTRAP_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_email_allowed(db: Session, email: str) -> bool:
    """Allow sign-in only for known users, pending invitees, or bootstrap emails."""
    email = email.strip().lower()
    if email in _bootstrap_emails():
        return True
    if db.query(User).filter(User.email == email).first():
        return True
    invite = (
        db.query(OrgInvite)
        .filter(
            OrgInvite.invited_email == email,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.expires_at > datetime.utcnow(),
        )
        .first()
    )
    return invite is not None


# ---------------------------------------------------------------------------
# Verification codes
# ---------------------------------------------------------------------------


def _hash_code(email: str, code: str) -> str:
    """sha256(secret || email || code) — keyed so DB exfiltration alone doesn't
    let an attacker pre-compute hashes for all 10^6 codes."""
    mac = hmac.new(SECRET_KEY.encode(), digestmod=hashlib.sha256)
    mac.update(email.lower().encode())
    mac.update(b"|")
    mac.update(code.encode())
    return mac.hexdigest()


def generate_code() -> str:
    """Six-digit numeric code. secrets.randbelow is uniform; zero-padded so
    leading-zero codes (e.g. 003421) are never rejected as 5 chars."""
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_code(db: Session, email: str) -> str:
    """Invalidate any prior codes for this email and store a fresh one.
    Returns the cleartext code so the caller can email it."""
    email = email.strip().lower()
    db.query(EmailVerificationCode).filter(EmailVerificationCode.email == email).delete()
    code = generate_code()
    row = EmailVerificationCode(
        email=email,
        code_hash=_hash_code(email, code),
        expires_at=datetime.utcnow() + timedelta(seconds=CODE_TTL_SECONDS),
        attempts=0,
    )
    db.add(row)
    db.commit()
    return code


def consume_code(db: Session, email: str, code: str) -> None:
    """Validate and consume a code. Raises HTTPException on any failure.

    Increments the attempt counter on bad-but-fresh codes so a brute-force
    against the 10^6 space is bounded by CODE_MAX_ATTEMPTS per issued code.
    """
    email = email.strip().lower()
    row = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == email)
        .order_by(EmailVerificationCode.id.desc())
        .first()
    )
    if not row or row.consumed_at:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    if datetime.utcnow() > row.expires_at:
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=400, detail="Code expired — request a new one")
    if row.attempts >= CODE_MAX_ATTEMPTS:
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=400, detail="Too many incorrect attempts — request a new code")

    expected = row.code_hash
    if not hmac.compare_digest(expected, _hash_code(email, code.strip())):
        row.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    row.consumed_at = datetime.utcnow()
    db.commit()


# ---------------------------------------------------------------------------
# Session cookies
# ---------------------------------------------------------------------------


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
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    current_version = getattr(user, "session_version", 0) or 0
    if session_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked — sign in again",
        )
    return user


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------


def send_verification_code(email: str, code: str) -> None:
    """Email the 6-digit code. Falls back to stdout in dev if RESEND_API_KEY unset."""
    from email_templates import verification_code_html

    from_address = os.getenv("FROM_EMAIL", "noreply@yourdomain.com")
    from_name = "Section"
    reply_to = os.getenv("REPLY_TO_EMAIL", f"no-reply@{from_address.split('@')[-1]}")

    expiry_min = CODE_TTL_SECONDS // 60
    html_body = verification_code_html(code, expiry_minutes=expiry_min)
    text_body = (
        f"Your Section sign-in code is: {code}\n\n"
        f"It expires in {expiry_min} minutes. If you didn't request this, ignore this email.\n"
    )

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print(f"\n[auth] Verification code for {email}: {code}\n", flush=True)
        return

    import resend

    resend.api_key = api_key
    resend.Emails.send(
        {
            "from": f"{from_name} <{from_address}>",
            "reply_to": reply_to,
            "to": email,
            "subject": f"Your Section sign-in code: {code}",
            "html": html_body,
            "text": text_body,
            "headers": {
                "List-Unsubscribe": f"<mailto:{reply_to}?subject=unsubscribe>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        }
    )
