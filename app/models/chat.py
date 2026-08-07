import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

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


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    # Supabase auth.users.id. 스키마 소유가 달라 FK는 걸지 않는다(논리 참조).
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
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
# 채팅방 목록의 "최근 연락순" 정렬 전용.
Index(
    "ix_chat_rooms_user_id_last_message_at",
    ChatRoom.user_id,
    ChatRoom.last_message_at.desc(),
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
