"""Room 안의 메시지, 음성·텍스트 턴, 피드백과 오디오 API."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from google import genai
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import FEEDBACK_MODEL, get_settings, get_tts_settings
from app.core.db import get_db
from app.core.guest import Actor, get_actor
from app.models.chat import ChatFeedback, ChatMessage, ChatRoomStatus
from app.routers.rooms import GUEST_MAX_TURNS, _get_room_or_404, _to_message_response
from app.schemas.room_conversation import (
    RoomConversationContext,
    RoomTurnResponse,
    TextRoomTurnRequest,
    VoiceRoomTurnRequest,
)
from app.schemas.rooms import (
    ChatMessageListResponse,
    FeedbackResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services import catalog
from app.services.conversation_pipeline import ConversationPipelineService
from app.services.feedback import (
    FEEDBACK_MESSAGE_LIMIT,
    FEEDBACK_PROMPT_VERSION,
    FeedbackMessage,
    FeedbackResult,
    generate_feedback,
)
from app.services.gemini_answer_audio_generator import GeminiAnswerAudioGenerator
from app.services.gemini_user_text_analyzer import GeminiUserTextAnalyzer
from app.services.llm import generate_answer, generate_structured_answer
from app.services.room_conversation import RoomConversationService

router = APIRouter(tags=["Room Conversation"])
HISTORY_LIMIT = 50


@lru_cache
def get_room_conversation_service() -> RoomConversationService:
    settings = get_settings()
    conversation = ConversationPipelineService(
        analyzer=GeminiUserTextAnalyzer(
            genai.Client(api_key=settings.gemini_api_key), settings.emotion_model
        ),
        chat_generator=generate_structured_answer,
        tts_service=GeminiAnswerAudioGenerator(get_tts_settings()),
    )
    return RoomConversationService(conversation, generate_feedback)


def _process_room_turn(
    room_id: str,
    request: TextRoomTurnRequest | VoiceRoomTurnRequest,
    actor: Actor,
    db: Session,
) -> RoomTurnResponse:
    room = _get_room_or_404(db, room_id, actor)
    if room.status is not ChatRoomStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="이미 종료된 채팅방입니다.")
    text = request.text if isinstance(request, TextRoomTurnRequest) else request.transcript
    clean_text = text.strip()
    history = [
        {"role": message.role, "content": message.content}
        for message in room.messages[-HISTORY_LIMIT:]
    ]

    user_message = ChatMessage(room_id=room.id, role="user", content=clean_text)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    persona = catalog.find_persona(db, room.persona_id)
    scenario = catalog.find_scenario(db, room.scenario_id) if room.scenario_id else None
    feedback_messages = [
        FeedbackMessage(id=message.id, role=message.role, content=message.content)
        for message in room.messages[-(FEEDBACK_MESSAGE_LIMIT - 1) :]
        if message.role in {"user", "assistant"} and message.id != user_message.id
    ]
    feedback_messages.append(
        FeedbackMessage(id=user_message.id, role="user", content=clean_text)
    )
    context = RoomConversationContext(
        room_id=room.id,
        user_id=actor.user_id or actor.guest_id or "unknown",
        persona_id=room.persona_id,
        persona_description=persona.description if persona else room.persona_id,
        scenario_description=scenario.description if scenario else None,
        communication_goal=scenario.communication_goal if scenario else None,
        history=history,
        feedback_messages=feedback_messages,
    )
    service = get_room_conversation_service()
    result = (
        service.process_text(request, context)
        if isinstance(request, TextRoomTurnRequest)
        else service.process_voice(request, context)
    )

    assistant_message = ChatMessage(
        room_id=room.id, role="assistant", content=result.conversation.answer
    )
    feedback = ChatFeedback(
        room_id=room.id,
        last_message_id=user_message.id,
        model=FEEDBACK_MODEL,
        prompt_version=FEEDBACK_PROMPT_VERSION,
        score=result.feedback.score,
        result_json=result.feedback.model_dump(mode="json"),
    )
    db.add_all([assistant_message, feedback])
    if actor.is_guest:
        room.turn_count += 1
        if room.turn_count >= GUEST_MAX_TURNS:
            room.status = ChatRoomStatus.COMPLETED
    db.commit()
    db.refresh(assistant_message)
    return RoomTurnResponse(
        room_id=room.id,
        user_message=_to_message_response(user_message),
        assistant_message=_to_message_response(assistant_message),
        conversation=result.conversation,
        feedback=result.feedback,
    )


@router.post("/rooms/{room_id}/turns/text", response_model=RoomTurnResponse)
def process_text_turn(
    room_id: str,
    request: TextRoomTurnRequest,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> RoomTurnResponse:
    return _process_room_turn(room_id, request, actor, db)


@router.post("/rooms/{room_id}/turns/voice", response_model=RoomTurnResponse)
def process_voice_turn(
    room_id: str,
    request: VoiceRoomTurnRequest,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> RoomTurnResponse:
    return _process_room_turn(room_id, request, actor, db)


@router.get("/rooms/{room_id}/audio/{filename}", response_class=FileResponse)
def get_generated_audio(
    room_id: str,
    filename: str,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> FileResponse:
    _get_room_or_404(db, room_id, actor)
    if Path(filename).name != filename or not filename.lower().endswith(".wav"):
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다.")
    output_dir = get_tts_settings().output_dir.resolve()
    audio_path = (output_dir / filename).resolve()
    if audio_path.parent != output_dir or not audio_path.is_file():
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다.")
    return FileResponse(audio_path, media_type="audio/wav", filename=filename)


@router.get("/rooms/{room_id}/messages", response_model=ChatMessageListResponse)
def list_messages(
    room_id: str,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> ChatMessageListResponse:
    room = _get_room_or_404(db, room_id, actor)
    return ChatMessageListResponse(
        messages=[_to_message_response(message) for message in room.messages]
    )


@router.post("/rooms/{room_id}/messages", response_model=SendMessageResponse)
def send_message(
    room_id: str,
    request: SendMessageRequest,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    """기존 텍스트 메시지 API 호환 경로. 새 앱은 turns/text를 사용한다."""

    room = _get_room_or_404(db, room_id, actor)
    if room.status is not ChatRoomStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="이미 종료된 채팅방입니다.")
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

    response_style = None
    if request.analysis is not None:
        generation = generate_structured_answer(
            question,
            persona=room.persona_id,
            history=history,
            analysis=request.analysis.model_dump(mode="json"),
        )
        answer = generation.answer
        response_style = generation.response_style
    else:
        answer = generate_answer(question, persona=room.persona_id, history=history)

    assistant_message = ChatMessage(room_id=room.id, role="assistant", content=answer)
    db.add(assistant_message)
    if actor.is_guest:
        room.turn_count += 1
        if room.turn_count >= GUEST_MAX_TURNS:
            room.status = ChatRoomStatus.COMPLETED
    db.commit()
    return SendMessageResponse(
        answer=answer,
        response_style=response_style,
        message=_to_message_response(assistant_message),
    )


@router.post("/rooms/{room_id}/feedback", response_model=FeedbackResponse)
def request_feedback(
    room_id: str,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """기존 수동 피드백 API. 새 turns API는 피드백을 자동 반환한다."""

    room = _get_room_or_404(db, room_id, actor)
    if actor.is_guest:
        raise HTTPException(status_code=403, detail="게스트 대화에는 수동 피드백을 제공하지 않습니다.")
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
    persona = catalog.find_persona(db, room.persona_id)
    scenario = catalog.find_scenario(db, room.scenario_id) if room.scenario_id else None
    result = generate_feedback(
        messages,
        persona=persona.description if persona else room.persona_id,
        scenario=scenario.description if scenario else room.scenario_id,
        communication_goal=scenario.communication_goal if scenario else None,
        user_id=actor.user_id or actor.guest_id,
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
