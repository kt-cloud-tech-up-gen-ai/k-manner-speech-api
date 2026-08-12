"""로그인·프로필 API의 요청/응답 DTO."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.user import Gender, LearningGoal, StudyFrequency

# 앞뒤 공백을 걷어낸 뒤 비면 안 된다(app/schemas/rooms.py의 CatalogId 선례).
# 이메일 형식·비밀번호 정책 검증은 Supabase에 위임하고 서버는 빈 값만 거른다.
_NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AuthUser(BaseModel):
    """인증된 사용자(= Supabase auth.users)."""

    id: str
    email: str | None = None
    role: str | None = None


class SignupRequest(BaseModel):
    """회원가입 요청. email·password가 빈 문자열이거나 공백뿐이면 422로 거부한다."""

    email: _NonBlankStr = Field(description="가입할 이메일. 형식 검증은 Supabase가 한다")
    password: _NonBlankStr = Field(
        description="비밀번호. 길이·복잡도 정책은 Supabase가 검증한다(위반 시 400)"
    )


class LoginResponse(BaseModel):
    """Legacy token response shape retained for internal Supabase parsing tests."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None
    user: AuthUser | None = None


class AuthSessionResponse(BaseModel):
    """Browser-visible auth response. Tokens live only in HttpOnly cookies."""

    user: AuthUser


class NativeLanguage(str, Enum):
    """모국어. 현재 서비스가 지원하는 값만 허용한다.

    DB 컬럼(user_profiles.native_language)은 varchar 그대로이며 제약을 추가하지 않았다.
    지원 언어가 늘어나면 여기에 값을 추가하면 된다.
    """

    KO = "ko"
    EN = "en"


class ProfileResponse(BaseModel):
    """온보딩 설정. 프로필 행이 없으면 모든 값이 비어 있는 기본값으로 응답한다."""

    name: str | None = None
    age: int | None = None
    learning_goal_other: str | None = None
    # 쓰기는 NativeLanguage(ko/en)로 제한하지만, 읽기는 str로 열어둔다.
    # 컬럼에 DB 제약이 없어 다른 값(예: "en-US")이 직접 들어갈 수 있고,
    # 그때 조회가 500으로 죽는 것보다 저장된 값을 그대로 돌려주는 편이 낫다.
    native_language: str | None = None
    gender: Gender | None = None
    learning_goals: list[LearningGoal] = []
    study_frequency: StudyFrequency | None = None
    push_enabled: bool = False
    # 프로필 행이 아직 없으면 null.
    updated_at: datetime | None = None


class MeResponse(BaseModel):
    user: AuthUser
    profile: ProfileResponse


class ProfileUpdateRequest(BaseModel):
    """전체 교체(PUT). 다섯 필드를 모두 명시해야 하며, 값으로 null은 허용한다."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    age: int | None = Field(default=None, ge=1, le=120)
    learning_goal_other: str | None = Field(default=None, max_length=500)
    native_language: NativeLanguage | None = Field(...)
    gender: Gender | None = Field(...)
    learning_goals: list[LearningGoal] = Field(...)
    study_frequency: StudyFrequency | None = Field(...)
    push_enabled: bool = Field(...)
