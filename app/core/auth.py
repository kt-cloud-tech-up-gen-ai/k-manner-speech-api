"""Supabase Auth 연동.

의존성 추가 없이 표준 라이브러리(urllib)로 Supabase Auth REST를 호출한다
(app/services/gemini.py의 Gemini 호출과 같은 방식).

토큰 검증은 매 요청마다 Supabase `GET /auth/v1/user`를 호출한다.
TODO(auth): 요청당 왕복 1회가 부담되면 JWKS 기반 로컬 JWT 검증으로 교체할 것.
"""

import json
import logging
import os
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.schemas.auth import AuthUser

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10

# auto_error=False: 게스트 허용 엔드포인트에서 토큰이 없어도 401을 내지 않게 한다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_supabase_url() -> str:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_URL이 설정되지 않았습니다.",
        )
    return url.rstrip("/")


def get_supabase_anon_key() -> str:
    """공개용 클라이언트 키.

    Supabase가 키 이름을 바꿔서(anon -> Publishable) 두 변수명을 모두 받는다.
    값 형식은 `sb_publishable_...`(신규) 또는 `eyJ...`(레거시 anon JWT) 둘 다 동작한다.
    """
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_ANON_KEY(또는 SUPABASE_PUBLISHABLE_KEY)가 설정되지 않았습니다.",
        )
    return key


def _call_supabase(path: str, *, method: str, headers: dict[str, str], body: Any = None) -> dict:
    url = f"{get_supabase_url()}/auth/v1{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = UrlRequest(url, data=data, method=method)
    request.add_header("apikey", get_supabase_anon_key())
    request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name, value)

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        logger.warning("Supabase Auth 오류: %s %s %s", method, path, payload)
        raise
    except URLError as exc:
        logger.exception("Supabase Auth 연결 실패: %s", path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="인증 서버에 연결할 수 없습니다.",
        ) from exc


def sign_in_with_password(email: str, password: str) -> dict:
    """이메일/비밀번호 로그인. 성공 시 Supabase 세션(access_token 등)을 반환한다."""
    try:
        return _call_supabase(
            "/token?grant_type=password",
            method="POST",
            headers={},
            body={"email": email, "password": password},
        )
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _fetch_user(token: str) -> AuthUser | None:
    try:
        payload = _call_supabase(
            "/user", method="GET", headers={"Authorization": f"Bearer {token}"}
        )
    except HTTPError:
        return None

    user_id = payload.get("id")
    if not user_id:
        return None
    return AuthUser(id=user_id, email=payload.get("email"), role=payload.get("role"))


def allow_guest(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> AuthUser | None:
    """게스트 허용. 유효한 토큰이 있으면 사용자, 없거나 잘못됐으면 None을 반환한다.

    사용 예: `user: AuthUser | None = Depends(allow_guest)`
    """
    if not token:
        return None
    return _fetch_user(token)


def require_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> AuthUser:
    """로그인 필수. 토큰이 없거나 유효하지 않으면 401.

    사용 예: `user: AuthUser = Depends(require_user)`
    또는 라우터 전체 보호: `APIRouter(dependencies=[Depends(require_user)])`
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _fetch_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 유효하지 않거나 만료되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[AuthUser, Depends(require_user)]
OptionalUser = Annotated[AuthUser | None, Depends(allow_guest)]
