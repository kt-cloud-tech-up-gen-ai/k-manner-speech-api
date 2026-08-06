from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.auth import AuthUser, CurrentUser, sign_in_with_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginResponse(BaseModel):
    """Swagger Authorize 및 일반 클라이언트가 함께 쓰는 로그인 응답."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None
    user: AuthUser | None = None


@router.post("/login", response_model=LoginResponse, summary="이메일/비밀번호 로그인")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> LoginResponse:
    """Supabase Auth 로그인.

    Swagger 우측 상단 **Authorize** 버튼에서 username(=이메일)/password를 입력하면
    발급된 access_token이 이후 요청의 Authorization 헤더에 자동으로 붙는다.
    """
    session = sign_in_with_password(form.username, form.password)
    user = session.get("user") or {}
    return LoginResponse(
        access_token=session["access_token"],
        token_type=session.get("token_type", "bearer"),
        refresh_token=session.get("refresh_token"),
        expires_in=session.get("expires_in"),
        user=AuthUser(id=user["id"], email=user.get("email"), role=user.get("role"))
        if user.get("id")
        else None,
    )


@router.get("/me", response_model=AuthUser, summary="현재 로그인 사용자")
def me(user: CurrentUser) -> AuthUser:
    return user
