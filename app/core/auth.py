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

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.schemas.auth import AuthUser

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10

# auto_error=False: 게스트 허용 엔드포인트에서 토큰이 없어도 401을 내지 않게 한다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# POST /auth/signup 전용. 400·409는 sign_up_with_password의 Supabase 오류 매핑이고,
# 503은 설정 부재 외에 Confirm email ON(가입 즉시 로그인 불가) 안내도 겸한다.
SIGNUP_ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    400: {"description": "비밀번호 정책 위반 또는 가입 거부"},
    409: {"description": "이미 가입된 이메일입니다."},
    502: {"description": "인증 서버에 연결할 수 없습니다."},
    503: {
        "description": (
            "Supabase 인증이 구성되지 않았거나, 이메일 확인(Confirm email)이 켜져 있어"
            " 가입 즉시 로그인할 수 없습니다."
        )
    },
}

# DELETE /auth/me 전용. CurrentUser 공통 오류(401)와 탈퇴 고유 오류(502·503)를 함께 담는다.
# 401만 적으면 부족하다. 토큰 검증이 매 요청 Supabase를 호출하므로(위 모듈 docstring),
# 설정이 비었거나 인증 서버에 닿지 못하면 401이 아니라 503·502가 그대로 클라이언트까지 간다.
WITHDRAW_ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "토큰이 없거나 만료되었습니다."},
    502: {"description": "회원 탈퇴 처리 중 인증 서버 오류가 발생했습니다."},
    503: {"description": "SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다."},
}


class SupabaseAuthError(Exception):
    """Supabase Auth가 4xx/5xx를 반환했다. 상태 코드와 파싱된 오류 본문을 보존한다.

    urllib의 HTTPError는 본문을 한 번 읽으면 버려지므로, _call_supabase가 본문을
    읽어 이 예외로 재포장한다. 소비처가 error_code 기반 매핑(가입 등)을 할 수 있다.
    """

    def __init__(self, status_code: int, payload: dict) -> None:
        super().__init__(f"Supabase Auth 오류 (HTTP {status_code})")
        self.status_code = status_code
        self.payload = payload


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


def get_supabase_service_role_key() -> str:
    """서버 전용 비밀 키(Admin API). 회원 탈퇴에서만 쓰며 클라이언트에 노출하지 않는다."""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.",
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
            raw = response.read()
            # Admin DELETE처럼 성공이어도 본문이 빈 응답이 있다 — {}로 취급한다.
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("Supabase Auth 오류: %s %s %s", method, path, body)
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        raise SupabaseAuthError(exc.code, parsed) from exc
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
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def refresh_session(refresh_token: str) -> dict:
    """Exchange a Supabase refresh token for a rotated session."""
    try:
        return _call_supabase(
            "/token?grant_type=refresh_token",
            method="POST",
            headers={},
            body={"refresh_token": refresh_token},
        )
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 만료되었습니다. 다시 로그인해 주세요.",
        ) from exc


def _raise_duplicate_email() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="이미 가입된 이메일입니다.",
    )


def sign_up_with_password(email: str, password: str) -> dict:
    """이메일/비밀번호 회원가입. 성공 시 Supabase 세션 payload(access_token 등)를 반환한다."""
    try:
        payload = _call_supabase(
            "/signup",
            method="POST",
            headers={},
            body={"email": email, "password": password},
        )
    except SupabaseAuthError as exc:
        # 신규 API는 error_code를 주고, 구버전 GoTrue는 msg 문구만 준다.
        error_code = exc.payload.get("error_code") or (
            "user_already_exists"
            if "already registered" in str(exc.payload.get("msg", ""))
            else None
        )
        if error_code in {"user_already_exists", "email_exists"}:
            _raise_duplicate_email()
        if error_code == "weak_password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="비밀번호가 정책에 맞지 않습니다.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="가입 요청이 거부되었습니다.",
        ) from exc

    # Confirm email이 켜져 있으면 Supabase가 중복 가입에도 200을 주되, user 열람 방지를
    # 위해 identities만 빈 배열로 숨긴다. 이 은닉 응답도 중복으로 간주해 409로 매핑한다.
    user = payload.get("user") or payload
    if user.get("identities") == []:
        _raise_duplicate_email()
    return payload


def delete_user_account(user_id: str) -> None:
    """Supabase Auth 계정을 완전히 삭제한다(Admin API).

    이미 삭제된 계정(404)은 성공으로 간주한다 — 재시도해도 같은 결과인 멱등 동작(A3).
    """
    # Supabase에 요청을 보내기 전에 키부터 확인해, 미설정이면 503으로 사전 차단한다.
    key = get_supabase_service_role_key()
    try:
        _call_supabase(
            f"/admin/users/{user_id}",
            method="DELETE",
            # urllib의 add_header는 같은 이름의 헤더를 덮어쓴다. _call_supabase가 먼저
            # 넣는 anon 기본 apikey가 여기서 준 service_role 키로 교체된다.
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
    except SupabaseAuthError as exc:
        if exc.status_code == 404:
            return
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="회원 탈퇴 처리 중 인증 서버 오류가 발생했습니다.",
        ) from exc


def _fetch_user(token: str) -> AuthUser | None:
    try:
        payload = _call_supabase(
            "/user", method="GET", headers={"Authorization": f"Bearer {token}"}
        )
    except SupabaseAuthError:
        return None

    user_id = payload.get("id")
    if not user_id:
        return None
    return AuthUser(id=user_id, email=payload.get("email"), role=payload.get("role"))


def allow_guest(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> AuthUser | None:
    """게스트 허용. 유효한 토큰이 있으면 사용자, 없거나 잘못됐으면 None을 반환한다.

    사용 예: `user: AuthUser | None = Depends(allow_guest)`
    """
    token = request.cookies.get("access_token") or token
    if not token:
        return None
    return _fetch_user(token)


def require_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> AuthUser:
    """로그인 필수. 토큰이 없거나 유효하지 않으면 401.

    사용 예: `user: AuthUser = Depends(require_user)`
    또는 라우터 전체 보호: `APIRouter(dependencies=[Depends(require_user)])`
    """
    token = request.cookies.get("access_token") or token
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
