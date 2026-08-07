import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    persona_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
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
