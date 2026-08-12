"""대화 상대(persona) / 시나리오(mode) 카탈로그 모델.

이 두 테이블과 둘을 잇는 `persona_scenarios`가 카탈로그의 SSOT다. 값의 의미와 API 노출 형태는
`app/schemas/catalog.py`의 DTO가, 각 값이 없을 때/있을 때의 동작은
`tests/test_catalog_model.py`와 `tests/test_catalog_service.py`가 규정한다.

id는 URL·요청 본문에 그대로 실리는 사람이 읽는 식별자(예: "doyun", "interview")라
자연키로 둔다. 서로게이트 키를 쓰면 클라이언트가 의미 없는 UUID를 다뤄야 한다.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, enum_column
from app.models.user import Gender

# chat_rooms.persona_id / scenario_id와 같은 폭을 쓴다(뒤에 FK를 걸기 때문).
_ID_LENGTH = 64


def _now() -> datetime:
    return datetime.now(timezone.utc)


# persona ↔ scenario는 N:N이다. 한 상대와 여러 상황을 연습할 수 있고, 같은 상황을
# 여러 상대와 연습할 수 있다. 이 표에 없는 조합은 "그 상대로는 아직 준비되지 않은 상황"이며
# 채팅방 생성이 거부된다(연결 컬럼 외 속성이 없어 ORM 클래스 없이 Core Table로 둔다).
#
# 카탈로그 행이 사라지면 이 매핑이 가리킬 곳이 없어지므로 chat_rooms와 같은 RESTRICT를 쓴다.
# 단, RESTRICT는 DB 계층 제약이라 SQL DELETE에만 걸린다. ORM으로 persona/scenario를
# 지우면 SQLAlchemy가 secondary 행을 먼저 정리하므로 제약에 닿지 않는다.
persona_scenarios = Table(
    "persona_scenarios",
    Base.metadata,
    Column(
        "persona_id",
        String(_ID_LENGTH),
        ForeignKey("personas.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "scenario_id",
        String(_ID_LENGTH),
        ForeignKey("scenarios.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class Persona(Base):
    """대화 상대. `GET /personas` 응답과 `chat_rooms.persona_id`의 참조 대상.

    나이·성별·사용자와의 관계는 말투와 호칭을 결정하는 값이라 필수다. 셋 중 하나라도
    비면 대화 프롬프트를 만들 수 없으므로 NULL을 허용하지 않는다.
    이름만 예외로, 한국어 이름처럼 middle/last가 없는 persona가 있어 first_name만 필수다.
    """

    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(_ID_LENGTH), primary_key=True)

    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 만 나이. 사용자와의 나이 차가 존댓말/반말 선택에 쓰인다.
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    # 사용자 프로필과 같은 Gender enum을 쓴다(VARCHAR + CHECK 제약).
    gender: Mapped[Gender] = mapped_column(
        enum_column(Gender, "ck_personas_gender"), nullable=False
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    # 사용자와 이 persona의 관계(예: "같은 학교 선배"). 호칭과 존대 수준을 정한다.
    relationship_description: Mapped[str] = mapped_column(Text, nullable=False)

    headline: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    # persona 정의가 바뀐 시각. 캐시 무효화·재현성 추적용이라 갱신 시 자동으로 올라간다.
    version: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # 이 상대로 고를 수 있는 시나리오. persona 상세 응답에 그대로 실린다.
    # id 오름차순은 목록 API(`list_scenarios`)와 같은 순서를 보장하기 위한 것이다.
    scenarios: Mapped[list["Scenario"]] = relationship(
        secondary=persona_scenarios,
        back_populates="personas",
        order_by="Scenario.id",
    )


class Scenario(Base):
    """대화 시나리오(모드). `chat_rooms.scenario_id`는 선택값이라 방 쪽에서 nullable.

    시나리오는 "무엇을 달성하면 성공인가"와 "언제 끝나는가"가 있어야 성립하므로
    communication_goal·end_condition·max_turns는 필수다.
    시간·공간은 배경 묘사라 없으면 없는 대로 프롬프트를 만들 수 있어 선택값이다.
    """

    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(_ID_LENGTH), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # 시간 맥락(예: "평일 저녁 7시", "점심시간"). 배경 묘사라 선택값.
    time_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 공간 맥락(예: "회사 근처 카페"). 배경 묘사라 선택값.
    place_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 이 대화에서 사용자가 달성해야 하는 의사소통 목표. 피드백 채점 기준이 된다.
    communication_goal: Mapped[str] = mapped_column(Text, nullable=False)
    # 대화를 끝내도 되는 조건(목표 달성 판정 기준).
    end_condition: Mapped[str] = mapped_column(Text, nullable=False)
    # 턴 상한. 종료 조건이 걸리지 않아도 이 턴 수에서 대화를 마무리한다.
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    # max_turns에 도달했는데 종료 조건을 못 채웠을 때 persona가 대화를 매듭짓는 말
    # (예: "수업 시간이 되어서 가봐야 해"). 이때 방은 FAILED가 된다.
    # 없으면 이 시나리오에 전용 마무리 대사가 없다는 뜻이다.
    turn_limit_exit_line: Mapped[str | None] = mapped_column(Text, nullable=True)

    title_ko: Mapped[str] = mapped_column(String(160), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(160), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_featured: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    # 시나리오 정의가 바뀐 시각. Persona.version과 같은 규칙.
    version: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # 이 상황을 연습할 수 있는 상대. scenario 상세 응답에 그대로 실린다.
    personas: Mapped[list[Persona]] = relationship(
        secondary=persona_scenarios,
        back_populates="scenarios",
        order_by=Persona.id,
    )


Index("ix_personas_active_sort", Persona.is_active, Persona.sort_order, Persona.id)
Index(
    "ix_scenarios_active_featured_sort",
    Scenario.is_active,
    Scenario.is_featured,
    Scenario.sort_order,
    Scenario.id,
)
