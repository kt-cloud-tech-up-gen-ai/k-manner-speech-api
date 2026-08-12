from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import (
    SIGNUP_ERROR_RESPONSES,
    WITHDRAW_ERROR_RESPONSES,
    CurrentUser,
    delete_user_account,
    refresh_session,
    sign_in_with_password,
    sign_up_with_password,
)
from app.core.db import get_db
from app.models.chat import ChatRoom
from app.models.user import UserLearningGoal, UserProfile
from app.schemas.auth import (
    AuthSessionResponse,
    AuthUser,
    LoginResponse,
    MeResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    SignupRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
GUEST_COOKIE = "guest_session"


def _set_session_cookies(response: Response, session: dict) -> None:
    from app.core.csrf import CSRF_COOKIE, new_csrf_token

    response.set_cookie(
        ACCESS_COOKIE,
        session["access_token"],
        max_age=session.get("expires_in"),
        httponly=True,
        samesite="lax",
        secure=False,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        session["refresh_token"],
        httponly=True,
        samesite="lax",
        secure=False,
    )
    response.set_cookie(CSRF_COOKIE, new_csrf_token(), httponly=False, samesite="lax")
    response.delete_cookie(GUEST_COOKIE)


def _browser_session(session: dict) -> AuthSessionResponse:
    parsed = _to_login_response(session)
    if parsed.user is None:
        raise HTTPException(status_code=502, detail="인증 사용자 정보가 없습니다.")
    return AuthSessionResponse(user=parsed.user)


def _purge_request_guest(request: Request, db: Session) -> None:
    from app.core.guest import decode_guest_cookie

    guest_id = decode_guest_cookie(request.cookies.get(GUEST_COOKIE))
    if guest_id is None:
        return
    rooms = db.scalars(select(ChatRoom).where(ChatRoom.guest_id == guest_id)).all()
    for room in rooms:
        db.delete(room)
    db.commit()


def _to_login_response(session: dict) -> LoginResponse:
    """Supabase 세션 payload를 응답으로 조립한다. login·signup이 공유한다(계약 동일)."""
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


@router.post("/login", response_model=AuthSessionResponse, summary="이메일/비밀번호 로그인")
def login(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> AuthSessionResponse:
    """Supabase Auth 로그인.

    Swagger 우측 상단 **Authorize** 버튼에서 username(=이메일)/password를 입력하면
    발급된 access_token이 이후 요청의 Authorization 헤더에 자동으로 붙는다.
    """
    session = sign_in_with_password(form.username, form.password)
    _purge_request_guest(request, db)
    _set_session_cookies(response, session)
    return _browser_session(session)


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthSessionResponse,
    summary="이메일/비밀번호 회원가입",
    responses=SIGNUP_ERROR_RESPONSES,
)
def signup(
    request: Request,
    response: Response,
    payload: SignupRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthSessionResponse:
    """이메일과 비밀번호로 계정을 만든다. 성공하면 즉시 로그인 상태가 된다.

    응답은 로그인(POST /auth/login)과 같은 형태다. 받은 access_token을 이후 요청의
    `Authorization: Bearer <token>` 헤더에 붙이면 바로 다른 API를 쓸 수 있다.
    프로필(온보딩)은 가입 후 `PUT /auth/me/profile`로 저장한다.
    """
    session = sign_up_with_password(payload.email, payload.password)
    # Confirm email이 켜져 있으면 Supabase가 세션 없이 user만 돌려준다(A1). 즉시 로그인
    # 계약을 지킬 수 없으므로 조용히 넘기지 않고 설정 안내와 함께 503을 낸다.
    if "access_token" not in session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="이메일 확인(Confirm email)이 켜져 있어 가입 즉시 로그인할 수 없습니다. Supabase 설정을 확인하세요.",
        )
    _purge_request_guest(request, db)
    _set_session_cookies(response, session)
    return _browser_session(session)


@router.post("/refresh", response_model=AuthSessionResponse, summary="세션 갱신")
def refresh(response: Response, refresh_token: Annotated[str | None, Cookie()] = None):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="갱신할 세션이 없습니다.")
    session = refresh_session(refresh_token)
    _set_session_cookies(response, session)
    return _browser_session(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="로그아웃")
def logout(response: Response) -> None:
    from app.core.csrf import CSRF_COOKIE

    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE, GUEST_COOKIE):
        response.delete_cookie(name)


EMPTY_PROFILE = ProfileResponse()


def _load_profile(db: Session, owner_id: str) -> UserProfile | None:
    # 매개변수 이름이 user_id가 아닌 이유: 탈퇴(_purge_user_data)의 삭제 필터 등치 조건
    # 리터럴이 파일 내에서 유일해야 한다(mutation 검증 앵커).
    return db.scalar(
        select(UserProfile)
        .options(selectinload(UserProfile.learning_goals))
        .where(UserProfile.user_id == owner_id)
    )


def _to_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        name=profile.name,
        age=profile.age,
        learning_goal_other=profile.learning_goal_other,
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

    profile.name = payload.name
    profile.age = payload.age
    profile.learning_goal_other = payload.learning_goal_other
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


def _purge_user_data(db: Session, user_id: str) -> None:
    """탈퇴 사용자의 앱 데이터를 트랜잭션에 삭제 준비만 한다. 커밋은 호출자 몫이다(A2).

    공유 Supabase DB이므로 user_id 등치 조건으로만 정밀 삭제한다 — 일괄 delete 금지.
    """
    # 방을 ORM으로 지우면 cascade가 메시지·피드백을 함께 지운다(rooms.py delete_room 선례).
    rooms = db.scalars(select(ChatRoom).where(ChatRoom.user_id == user_id)).all()
    for room in rooms:
        db.delete(room)

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is not None:
        # user_learning_goals는 cascade="all, delete-orphan"으로 함께 삭제된다.
        db.delete(profile)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴",
    responses=WITHDRAW_ERROR_RESPONSES,
)
def withdraw(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    """계정을 영구 삭제한다. 되돌릴 수 없다.

    모든 대화(채팅방·메시지·피드백)와 프로필·학습 목표가 함께 삭제되고 계정 자체가
    소멸한다. 성공은 본문 없이 204이며, 이후 기존 토큰으로는 어떤 API도 쓸 수 없다.
    """
    # A2 순서: 앱 데이터 삭제를 트랜잭션에 준비해 두고, Supabase Admin 삭제(계정 소멸)가
    # 성공한 경우에만 커밋한다. Admin 호출이 502/503으로 실패하면 커밋하지 않은 변경이
    # 그대로 폐기되어 앱 데이터가 보존된다. Admin 성공 후 커밋 실패라는 드문 창에서는
    # 고아 행이 남을 수 있으나 계정이 소멸해 접근 불가하므로 무해하다.
    _purge_user_data(db, user.id)
    delete_user_account(user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
