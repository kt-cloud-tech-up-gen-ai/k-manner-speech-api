"""Signed anonymous identity and unified room ownership."""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response

from app.core.auth import AuthUser, OptionalUser
from app.core.csrf import CSRF_COOKIE, new_csrf_token

GUEST_COOKIE = "guest_session"


def _secret() -> bytes:
    value = os.getenv("GUEST_SESSION_SECRET")
    if not value or len(value) < 32:
        raise HTTPException(status_code=503, detail="GUEST_SESSION_SECRET이 설정되지 않았습니다.")
    return value.encode()


def encode_guest_id(guest_id: str) -> str:
    signature = hmac.new(_secret(), guest_id.encode(), hashlib.sha256).hexdigest()
    return f"{guest_id}.{signature}"


def decode_guest_cookie(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    guest_id, signature = value.rsplit(".", 1)
    expected = hmac.new(_secret(), guest_id.encode(), hashlib.sha256).hexdigest()
    return guest_id if guest_id and hmac.compare_digest(signature, expected) else None


@dataclass(frozen=True)
class Actor:
    user: AuthUser | None = None
    guest_id: str | None = None

    @property
    def user_id(self) -> str | None:
        return self.user.id if self.user else None

    @property
    def is_guest(self) -> bool:
        return self.user is None


def get_actor(request: Request, response: Response, user: OptionalUser) -> Actor:
    if user is not None:
        return Actor(user=user)
    guest_id = decode_guest_cookie(request.cookies.get(GUEST_COOKIE)) or secrets.token_urlsafe(24)
    response.set_cookie(
        GUEST_COOKIE, encode_guest_id(guest_id), httponly=True, samesite="lax", secure=False
    )
    if not request.cookies.get(CSRF_COOKIE):
        response.set_cookie(CSRF_COOKIE, new_csrf_token(), httponly=False, samesite="lax")
    return Actor(guest_id=guest_id)
