"""대화 상대(persona) / 시나리오(mode) 카탈로그 모델.

이 두 테이블이 카탈로그의 SSOT다. 값의 의미와 API 노출 형태는
`app/schemas/catalog.py`의 DTO가, 각 값이 없을 때/있을 때의 동작은
`tests/test_catalog_model.py`와 `tests/test_catalog_service.py`가 규정한다.

id는 URL·요청 본문에 그대로 실리는 사람이 읽는 식별자(예: "doyun", "interview")라
자연키로 둔다. 서로게이트 키를 쓰면 클라이언트가 의미 없는 UUID를 다뤄야 한다.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, enum_column
from app.models.user import Gender

# chat_rooms.persona_id / scenario_id와 같은 폭을 쓴다(뒤에 FK를 걸기 때문).
_ID_LENGTH = 64


def _now() -> datetime:
    return datetime.now(timezone.utc)


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

    # ElevenLabs TTS 음성 id. 음성을 붙이지 않은 persona가 있어 nullable.
    voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # persona 정의가 바뀐 시각. 캐시 무효화·재현성 추적용이라 갱신 시 자동으로 올라간다.
    version: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
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

    # 시나리오 정의가 바뀐 시각. Persona.version과 같은 규칙.
    version: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
