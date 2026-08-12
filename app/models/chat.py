import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, enum_column

# chat_rooms가 personas/scenarios를 FK로 참조하므로, 이 모듈만 임포트해도
# 참조 대상 테이블이 메타데이터에 등록되어 있어야 한다.
from app.models import catalog  # noqa: F401


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _same_as_created_at(context) -> datetime:
    """INSERT 시 created_at과 정확히 같은 값을 쓴다(_now()를 두 번 부르면 미세하게 어긋난다)."""
    return context.get_current_parameters()["created_at"]


class ChatRoomStatus(str, Enum):
    """시나리오 진행 상태.

    IN_PROGRESS를 뺀 셋은 모두 종료 상태이며, 종료된 방은 더 이상 대화를 받지 않는다.
    셋을 나누는 이유는 "왜 끝났는가"가 피드백·통계에서 서로 다른 의미를 갖기 때문이다.
    특히 COMPLETED와 FAILED는 둘 다 끝까지 간 대화지만 목표 달성 여부가 반대다.
    """

    IN_PROGRESS = "in_progress"
    # 시나리오의 종료 조건(communication_goal 달성)을 충족하고 끝났다.
    COMPLETED = "completed"
    # max_turns에 도달했는데 종료 조건을 충족하지 못했다. persona는
    # scenarios.turn_limit_exit_line으로 대화를 매듭짓는다.
    FAILED = "failed"
    # 사용자가 도중에 그만뒀다.
    ABANDONED = "abandoned"


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    # Supabase auth.users.id. 스키마 소유가 달라 FK는 걸지 않는다(논리 참조).
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    guest_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 카탈로그 행이 사라지면 이 방의 프롬프트를 재구성할 수 없으므로 RESTRICT.
    persona_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("personas.id", ondelete="RESTRICT"), nullable=False
    )
    scenario_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_same_as_created_at, onupdate=_now, nullable=False
    )
    # 마지막 연락 시간: 역할(user/assistant) 무관하게 가장 최근 메시지 시각.
    # 방 생성 직후에는 created_at과 같은 값으로 시작한다.
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_same_as_created_at, nullable=False
    )
    last_message_preview: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 읽음 처리 API(후속 작업)가 갱신한다.
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 진행 상태. 방을 만든 순간부터 대화가 시작된 것으로 보므로 기본값이 IN_PROGRESS다.
    status: Mapped[ChatRoomStatus] = mapped_column(
        enum_column(ChatRoomStatus, "ck_chat_rooms_status"),
        default=ChatRoomStatus.IN_PROGRESS,
        nullable=False,
    )
    # 진행한 턴 수. user 발화와 persona 응답이 모두 저장된 왕복 1회를 1턴으로 센다.
    # 메시지 수로 매번 계산하지 않고 컬럼에 두는 이유는 scenario.max_turns와 비교해
    # 종료를 판정하는 값이라, 목록 조회에서도 집계 없이 읽을 수 있어야 하기 때문이다.
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    feedbacks: Mapped[list["ChatFeedback"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="ChatFeedback.created_at",
    )


Index("ix_chat_rooms_user_id_created_at", ChatRoom.user_id, ChatRoom.created_at)
Index("ix_chat_rooms_guest_id_created_at", ChatRoom.guest_id, ChatRoom.created_at)
ChatRoom.__table__.append_constraint(
    CheckConstraint(
        "(user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL)",
        name="ck_chat_rooms_exactly_one_owner",
    )
)
# 채팅방 목록의 "최근 연락순" 정렬 전용.
#
# 방향은 붙이지 않는다. `WHERE user_id = ?`가 등치 조건이라 남는 정렬 키는 last_message_at
# 하나뿐이고, PostgreSQL은 이 인덱스를 거꾸로 훑어 `ORDER BY last_message_at DESC`를 그대로
# 처리한다. 실행 계획이 같으므로 DESC를 선언할 이유가 없다.
#
# 예전에는 `.desc()`가 붙어 있었는데 마이그레이션(7ea6b68d4729)은 방향 없이 만들고 있어
# 모델과 DB가 어긋나 있었다. SQLite는 인덱스 방향을 reflect하지 못해
# `test_head_schema_matches_models`가 이 차이를 잡지 못했고, 실제 PostgreSQL에
# 적용해 보고서야 드러났다.
Index(
    "ix_chat_rooms_user_id_last_message_at",
    ChatRoom.user_id,
    ChatRoom.last_message_at,
)

# 자유 수다 방(scenario 없는 방)은 사용자-persona 당 하나뿐이다.
# persona가 N개면 사용자는 최대 N개의 자유 수다 방을 갖는다.
#
# 시나리오가 있는 방은 이 인덱스의 대상이 아니므로 같은 조합으로 몇 개든 만들 수 있다.
# 부분 인덱스가 그 구분을 표현한다 — WHERE 절이 없으면 시나리오 방까지 하나로 묶여 버린다.
#
# sqlite_where와 postgresql_where를 **둘 다** 준다. 하나만 주면 다른 백엔드에서는 WHERE가
# 빠진 채 전체 유니크 인덱스가 만들어져, 개발 환경에서는 멀쩡한데 운영에서 시나리오 방
# 생성이 막힌다.
Index(
    "uq_chat_rooms_free_talk",
    ChatRoom.user_id,
    ChatRoom.persona_id,
    unique=True,
    sqlite_where=ChatRoom.scenario_id.is_(None),
    postgresql_where=ChatRoom.scenario_id.is_(None),
)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    room_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    room: Mapped[ChatRoom] = relationship(back_populates="messages")


Index("ix_chat_messages_room_id_created_at", ChatMessage.room_id, ChatMessage.created_at)


class ChatFeedback(Base):
    __tablename__ = "chat_feedbacks"
    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "last_message_id",
            "model",
            "prompt_version",
            name="uq_chat_feedback_context",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    room_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )
    last_message_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    room: Mapped[ChatRoom] = relationship(back_populates="feedbacks")


Index("ix_chat_feedbacks_room_id_created_at", ChatFeedback.room_id, ChatFeedback.created_at)
