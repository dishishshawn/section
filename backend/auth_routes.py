import os
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    make_magic_token,
    make_session_cookie,
    send_magic_link,
    verify_magic_token,
    SESSION_TTL_SECONDS,
)
from database import get_db
from models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "section_session"
_dev_mode = not os.getenv("RESEND_API_KEY")


class RequestLinkBody(BaseModel):
    email: str


class RequestLinkResponse(BaseModel):
    dev_link: str | None = None


class MeResponse(BaseModel):
    id: int
    email: str
    display_name: str | None

    model_config = {"from_attributes": True}


@router.post("/request-link", response_model=RequestLinkResponse)
def request_link(body: RequestLinkBody, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    token = make_magic_token(email)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    send_magic_link(email, token)
    if _dev_mode:
        app_url = os.getenv("APP_URL", "http://localhost:8000")
        return {"dev_link": f"{app_url}/api/auth/verify?token={token}"}
    return {}


@router.get("/verify")
def verify(token: str, response: Response, db: Session = Depends(get_db)):
    email = verify_magic_token(token)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    cookie = make_session_cookie(user.id)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=cookie,
        httponly=True,
        samesite="lax",
        secure=False,  # flip to True behind HTTPS in prod
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    response.headers["Location"] = "http://localhost:3000"
    response.status_code = 302
    return response


@router.post("/signout", status_code=204)
def signout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return user
