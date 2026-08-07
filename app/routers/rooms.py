from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import FEEDBACK_MODEL
from app.core.db import get_db
from app.models.chat import ChatFeedback, ChatMessage, ChatRoom
from app.routers.routers import generate_answer
from app.services import catalog
from app.services.feedback import (
    FEEDBACK_MESSAGE_LIMIT,
    FEEDBACK_PROMPT_VERSION,
    CategoryScores,
    FeedbackIssue,
    FeedbackMessage,
    FeedbackResult,
    generate_feedback,
)

router = APIRouter(tags=["rooms"])

HISTORY_LIMIT = 50

# TODO(KAN-47/auth): 인증이 없어 user_id를 요청 값 그대로 신뢰한다. 남의 room_id를 알면
#   조회·전송·피드백이 모두 가능하다. 인증 도입 시 요청자 == room.user_id 검사를 추가할 것.
# TODO(KAN-47/scale): 채팅방 목록·채팅 내역에 페이지네이션이 없다. 대화가 길어지면
#   전체 메시지를 한 번에 반환하므로 limit/cursor 파라미터가 필요하다.


class CreateRoomRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    persona_id: str = Field(min_length=1, max_length=64)
    scenario_id: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=200)


class RoomResponse(BaseModel):
    id: str
    user_id: str
    persona_id: str
    scenario_id: str | None
    title: str | None
    created_at: datetime


class RoomListResponse(BaseModel):
    rooms: list[RoomResponse]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    question: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    answer: str
    message: MessageResponse


class FeedbackResponse(BaseModel):
    score: int
    category_scores: CategoryScores
    summary: str
    strengths: list[str]
    improvements: list[str]
    issues: list[FeedbackIssue]
    cached: bool


def _get_room_or_404(db: Session, room_id: str) -> ChatRoom:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="채팅방을 찾을 수 없습니다."
        )
    return room


def _to_room_response(room: ChatRoom) -> RoomResponse:
    return RoomResponse(
        id=room.id,
        user_id=room.user_id,
        persona_id=room.persona_id,
        scenario_id=room.scenario_id,
        title=room.title,
        created_at=room.created_at,
    )


def _to_message_response(message: ChatMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(request: CreateRoomRequest, db: Session = Depends(get_db)) -> RoomResponse:
    """채팅방을 생성한다. (KAN-60)"""
    if catalog.find_persona(request.persona_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"알 수 없는 persona입니다: {request.persona_id}",
        )
    if request.scenario_id and catalog.find_scenario(request.scenario_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"알 수 없는 시나리오입니다: {request.scenario_id}",
        )

    room = ChatRoom(
        user_id=request.user_id,
        persona_id=request.persona_id,
        scenario_id=request.scenario_id,
        title=request.title,
    )
    db.add(room)
    db.commit()
    return _to_room_response(room)


@router.get("/rooms", response_model=RoomListResponse)
def list_rooms(
    user_id: str = Query(min_length=1), db: Session = Depends(get_db)
) -> RoomListResponse:
    """사용자의 채팅방 목록을 최신순으로 반환한다. (KAN-61)"""
    rooms = db.scalars(
        select(ChatRoom)
        .where(ChatRoom.user_id == user_id)
        .order_by(ChatRoom.created_at.desc())
    ).all()
    return RoomListResponse(rooms=[_to_room_response(room) for room in rooms])


@router.get("/rooms/{room_id}/messages", response_model=MessageListResponse)
def list_messages(room_id: str, db: Session = Depends(get_db)) -> MessageListResponse:
    """채팅방의 채팅 내역을 오래된 순으로 반환한다. (KAN-62)"""
    room = _get_room_or_404(db, room_id)
    return MessageListResponse(
        messages=[_to_message_response(message) for message in room.messages]
    )


@router.post("/rooms/{room_id}/messages", response_model=SendMessageResponse)
def send_message(
    room_id: str, request: SendMessageRequest, db: Session = Depends(get_db)
) -> SendMessageResponse:
    """사용자 메시지를 저장하고 persona 응답을 생성해 함께 저장한다. (KAN-65)

    TODO(KAN-59/KAN-65): room.scenario_id를 저장만 하고 프롬프트에는 반영하지 않는다.
      build_chat_prompt가 modes 번들을 받도록 확장해 시나리오(면접/역할극)를 적용할 것.
    """
    room = _get_room_or_404(db, room_id)

    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="질문을 입력해 주세요."
        )

    history = [
        {"role": message.role, "content": message.content}
        for message in room.messages[-HISTORY_LIMIT:]
    ]

    user_message = ChatMessage(room_id=room.id, role="user", content=question)
    db.add(user_message)
    db.commit()

    answer = generate_answer(question, persona=room.persona_id, history=history)

    assistant_message = ChatMessage(room_id=room.id, role="assistant", content=answer)
    db.add(assistant_message)
    db.commit()

    return SendMessageResponse(
        answer=answer, message=_to_message_response(assistant_message)
    )


@router.post("/rooms/{room_id}/feedback", response_model=FeedbackResponse)
def request_feedback(room_id: str, db: Session = Depends(get_db)) -> FeedbackResponse:
    """채팅방 대화에서 사용자 말투의 예절/매너를 평가한다. (KAN-63)"""
    room = _get_room_or_404(db, room_id)

    if not any(message.role == "user" for message in room.messages):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="피드백할 사용자 발화가 없습니다.",
        )

    last_message = room.messages[-1]
    existing = db.scalar(
        select(ChatFeedback).where(
            ChatFeedback.room_id == room.id,
            ChatFeedback.last_message_id == last_message.id,
            ChatFeedback.model == FEEDBACK_MODEL,
            ChatFeedback.prompt_version == FEEDBACK_PROMPT_VERSION,
        )
    )
    if existing is not None:
        result = FeedbackResult.model_validate(existing.result_json)
        return FeedbackResponse(**result.model_dump(), cached=True)

    messages = [
        FeedbackMessage(id=message.id, role=message.role, content=message.content)
        for message in room.messages[-FEEDBACK_MESSAGE_LIMIT:]
        if message.role in {"user", "assistant"}
    ]
    persona = catalog.find_persona(room.persona_id)
    scenario = catalog.find_scenario(room.scenario_id) if room.scenario_id else None
    result = generate_feedback(
        messages,
        persona=persona.description if persona else room.persona_id,
        scenario=scenario.description if scenario else room.scenario_id,
        user_id=room.user_id,
    )

    feedback = ChatFeedback(
        room_id=room.id,
        last_message_id=last_message.id,
        model=FEEDBACK_MODEL,
        prompt_version=FEEDBACK_PROMPT_VERSION,
        score=result.score,
        result_json=result.model_dump(mode="json"),
    )
    db.add(feedback)
    try:
        db.commit()
    except IntegrityError:
        # 동시에 같은 대화를 평가한 요청이 먼저 저장한 경우 기존 결과를 재사용한다.
        db.rollback()
        existing = db.scalar(
            select(ChatFeedback).where(
                ChatFeedback.room_id == room.id,
                ChatFeedback.last_message_id == last_message.id,
                ChatFeedback.model == FEEDBACK_MODEL,
                ChatFeedback.prompt_version == FEEDBACK_PROMPT_VERSION,
            )
        )
        if existing is None:
            raise
        result = FeedbackResult.model_validate(existing.result_json)
        return FeedbackResponse(**result.model_dump(), cached=True)

    return FeedbackResponse(**result.model_dump(), cached=False)
