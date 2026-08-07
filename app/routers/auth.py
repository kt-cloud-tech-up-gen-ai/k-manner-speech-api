from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import CurrentUser, sign_in_with_password
from app.core.db import get_db
from app.models.user import UserLearningGoal, UserProfile
from app.schemas.auth import (
    AuthUser,
    LoginResponse,
    MeResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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


EMPTY_PROFILE = ProfileResponse()


def _load_profile(db: Session, user_id: str) -> UserProfile | None:
    return db.scalar(
        select(UserProfile)
        .options(selectinload(UserProfile.learning_goals))
        .where(UserProfile.user_id == user_id)
    )


def _to_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        native_language=profile.native_language,
        gender=profile.gender,
        learning_goals=[row.goal for row in profile.learning_goals],
        study_frequency=profile.study_frequency,
        push_enabled=profile.push_enabled,
        updated_at=profile.updated_at,
    )


@router.get("/me", response_model=MeResponse, summary="현재 로그인 사용자와 프로필")
def me(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> MeResponse:
    """계정 정보와 온보딩 프로필을 함께 반환한다.

    프로필 행이 없으면 기본값을 반환하고 DB에는 쓰지 않는다(조회는 부작용이 없다).
    """
    profile = _load_profile(db, user.id)
    return MeResponse(
        user=user,
        profile=_to_response(profile) if profile is not None else EMPTY_PROFILE,
    )


@router.put(
    "/me/profile",
    response_model=ProfileResponse,
    summary="프로필 전체 교체(없으면 생성)",
)
def update_profile(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    payload: ProfileUpdateRequest,
) -> ProfileResponse:
    """온보딩 프로필을 요청 본문으로 통째로 덮어쓴다.

    learning_goals도 전체 교체다. 요청에 없는 목적은 삭제되고, 빈 배열이면 모두 해제된다.
    """
    profile = _load_profile(db, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.native_language = payload.native_language.value if payload.native_language else None
    profile.gender = payload.gender
    profile.study_frequency = payload.study_frequency
    profile.push_enabled = payload.push_enabled

    # (user_id, goal)이 복합 PK라 중복 입력은 제거한다. 입력 순서는 유지.
    goals = list(dict.fromkeys(payload.learning_goals))
    profile.learning_goals.clear()
    # 신규 프로필이면 goal 행보다 부모 행이 먼저 존재해야 FK를 만족한다.
    db.flush()
    profile.learning_goals.extend(
        UserLearningGoal(user_id=user.id, goal=goal) for goal in goals
    )

    db.commit()
    db.refresh(profile)
    return _to_response(profile)
