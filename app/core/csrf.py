"""Double-submit CSRF protection for cookie-authenticated mutations."""

import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import error_response

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PATHS = {"/auth/login", "/auth/signup"}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        has_session_cookie = bool(
            request.cookies.get("access_token") or request.cookies.get("guest_session")
        )
        if (
            request.method not in SAFE_METHODS
            and request.url.path not in EXEMPT_PATHS
            and has_session_cookie
        ):
            cookie = request.cookies.get(CSRF_COOKIE)
            header = request.headers.get(CSRF_HEADER)
            if not cookie or not header or not secrets.compare_digest(cookie, header):
                return error_response(
                    403, "CSRF_VALIDATION_FAILED", "요청을 확인할 수 없습니다. 다시 시도해 주세요."
                )
        return await call_next(request)
