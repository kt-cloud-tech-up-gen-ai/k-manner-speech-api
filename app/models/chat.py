import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


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
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    persona_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
