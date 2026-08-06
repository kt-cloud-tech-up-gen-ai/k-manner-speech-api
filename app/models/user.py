"""사용자 프로필(온보딩 설정) 모델.

계정 정보(이메일, 비밀번호, 가입 시각 등)는 Supabase `auth.users`가 관리한다.
여기서는 앱에서만 쓰는 설정값만 보관하고, 중복 컬럼은 두지 않는다.

PK는 Supabase user id(= AuthUser.id)이며 FK는 걸지 않는다(스키마/인스턴스 소유가 다름).
선택지가 정해진 값(성별·학습 목적·학습 빈도)은 아래 `str` Enum으로 정의하고
컬럼에도 그 타입을 매핑한다. DB 네이티브 enum은 쓰지 않는다(`_enum_column` 참고).
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_column(enum_type: type[Enum], constraint_name: str) -> SAEnum:
    """Enum을 VARCHAR + CHECK 제약으로 매핑한다.

    - native_enum=False: DB 네이티브 enum 타입을 만들지 않는다.
      PostgreSQL 네이티브 enum은 값 추가에 ALTER TYPE이 필요해 마이그레이션이 번거롭다.
    - name: native_enum=False에서는 CHECK 제약 이름이 된다.
    - values_callable: 저장 문자열을 멤버 이름(MALE)이 아니라 값(male)으로 고정한다.
      이 값이 그대로 API 요청/응답에 쓰인다.
    """
    return SAEnum(
        enum_type,
        name=constraint_name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda enum: [member.value for member in enum],
    )


class Gender(str, Enum):
    """성별. 미응답을 허용하므로 컬럼 자체는 nullable."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class LearningGoal(str, Enum):
    """주요 학습 목적(복수 선택). 선택된 값들은 user_learning_goals에 행으로 쌓인다."""

    DAILY_CONVERSATION = "daily_conversation"
    BUSINESS = "business"
    TRAVEL = "travel"
    EXAM = "exam"
    CULTURE = "culture"
    OTHER = "other"


class StudyFrequency(str, Enum):
    """학습 빈도(주당 목표)."""

    DAILY = "daily"
    FIVE_PER_WEEK = "five_per_week"
    THREE_PER_WEEK = "three_per_week"
    TWICE_PER_WEEK = "twice_per_week"
    WEEKLY = "weekly"


class UserProfile(Base):
    """온보딩에서 수집하는 사용자 설정.

    온보딩은 단계별로 진행되므로 설정값은 모두 nullable이다.
    프로필 행 자체가 아직 없을 수 있다는 점도 소비하는 쪽에서 처리해야 한다.
    """

    __tablename__ = "user_profiles"

    # Supabase auth.users.id. chat_rooms.user_id와 같은 폭을 쓴다.
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    # 1. 모국어 — BCP 47 언어 태그(예: "ko", "en-US").
    native_language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 2. 성별
    gender: Mapped[Gender | None] = mapped_column(
        _enum_column(Gender, "ck_user_profiles_gender"), nullable=True
    )

    # 4. 학습 빈도
    study_frequency: Mapped[StudyFrequency | None] = mapped_column(
        _enum_column(StudyFrequency, "ck_user_profiles_study_frequency"), nullable=True
    )

    # 5. 푸시 알림 수신 여부. 기기 토큰은 1:N이라 별도 테이블 몫이며 여기서는 다루지 않는다.
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # 3. 주요 학습 목적(복수 선택)
    learning_goals: Mapped[list["UserLearningGoal"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class UserLearningGoal(Base):
    """사용자별 학습 목적 1건. (user_id, goal) 복합 PK로 중복 선택을 막는다."""

    __tablename__ = "user_learning_goals"

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    goal: Mapped[LearningGoal] = mapped_column(
        _enum_column(LearningGoal, "ck_user_learning_goals_goal"), primary_key=True
    )

    profile: Mapped[UserProfile] = relationship(back_populates="learning_goals")
