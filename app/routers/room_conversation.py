"""Room 안의 메시지, 음성·텍스트 턴, 피드백과 오디오 API."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from google import genai
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import FEEDBACK_MODEL, get_settings, get_tts_settings
from app.core.db import get_db
from app.core.guest import Actor, get_actor
from app.models.catalog import Scenario
from app.models.chat import ChatFeedback, ChatMessage, ChatRoom, ChatRoomStatus
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
from app.schemas.voice_emotion import VoiceEmotionAnalysis, VoiceEmotionAnalysisRequest
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
from app.services.gemini_voice_emotion_analyzer import GeminiVoiceEmotionAnalyzer
from app.services.llm import generate_answer, generate_structured_answer
from app.services.media_storage import SupabaseMediaStorage
from app.services.room_conversation import RoomConversationService

router = APIRouter(tags=["Room Conversation"])
HISTORY_LIMIT = 50


def _advance_room_turn(
    room: ChatRoom, actor: Actor, scenario: Scenario | None, *, goal_achieved: bool
) -> bool:
    """왕복 대화 1회를 기록하고 종료 상태를 확정한다.

    게스트는 제품 체험 정책상 3턴까지만 허용하며, 상한 도달 시 completed로 마무리한다.
    로그인 사용자는 시나리오의 종료 조건(communication_goal) 충족 여부로 판정한다.
    조건을 충족하면 completed, 충족하지 못한 채 max_turns에 도달하면 failed다.

    반환값은 이번 턴이 "턴 상한으로 실패 종료된 턴"인지 여부다. True면 호출자가
    마지막 응답을 scenario.turn_limit_exit_line으로 대체한다.
    """
    room.turn_count += 1

    # 게스트 체험: 시나리오 종료 조건 개념이 없으므로 상한 도달만으로 completed.
    if actor.is_guest:
        if room.turn_count >= GUEST_MAX_TURNS:
            room.status = ChatRoomStatus.COMPLETED
        return False

    # 시나리오가 없는 자유 대화는 라우터 수준의 상한을 두지 않는다.
    if scenario is None:
        return False

    # 종료 조건을 충족했다면 상한과 무관하게 목표 달성으로 종료한다.
    if goal_achieved:
        room.status = ChatRoomStatus.COMPLETED
        return False

    # 상한에 도달했는데 종료 조건을 충족하지 못했다면 실패로 종료한다.
    if room.turn_count >= scenario.max_turns:
        room.status = ChatRoomStatus.FAILED
        return True

    return False


def _scenario_prompt_context(scenario: Scenario | None) -> dict[str, object] | None:
    """ORM 시나리오에서 대화 프롬프트에 필요한 값만 추출한다."""
    if scenario is None:
        return None
    return {
        "id": scenario.id,
        "description": scenario.description,
        "time_context": scenario.time_context,
        "place_context": scenario.place_context,
        "communication_goal": scenario.communication_goal,
        "end_condition": scenario.end_condition,
        "max_turns": scenario.max_turns,
        "turn_limit_exit_line": scenario.turn_limit_exit_line,
    }


@lru_cache
def get_room_conversation_service() -> RoomConversationService:
    settings = get_settings()
    conversation = ConversationPipelineService(
        analyzer=GeminiUserTextAnalyzer(
            genai.Client(api_key=settings.gemini_api_key), settings.emotion_model
        ),
        voice_analyzer=GeminiVoiceEmotionAnalyzer(
            genai.Client(api_key=settings.gemini_api_key), settings.voice_emotion_model
        ),
        chat_generator=generate_structured_answer,
        tts_service=GeminiAnswerAudioGenerator(get_tts_settings()),
    )
    return RoomConversationService(conversation, generate_feedback)


@lru_cache
def get_voice_emotion_analyzer() -> GeminiVoiceEmotionAnalyzer:
    settings = get_settings()
    return GeminiVoiceEmotionAnalyzer(
        genai.Client(api_key=settings.gemini_api_key), settings.voice_emotion_model
    )


@router.post("/voice/emotion-analysis", response_model=VoiceEmotionAnalysis)
def analyze_voice_emotion(
    request: VoiceEmotionAnalysisRequest,
    _actor: Actor = Depends(get_actor),
) -> VoiceEmotionAnalysis:
    """녹음 음성의 감정 비율과 상대가 받을 인상을 분석한다."""

    return get_voice_emotion_analyzer().analyze(
        audio_bytes=request.audio_bytes(),
        mime_type=request.audio_mime_type,
        transcript=request.transcript,
    )


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
    feedback_messages.append(FeedbackMessage(id=user_message.id, role="user", content=clean_text))
    context = RoomConversationContext(
        room_id=room.id,
        user_id=actor.user_id or actor.guest_id or "unknown",
        persona_id=room.persona_id,
        persona_description=persona.description if persona else room.persona_id,
        scenario_description=scenario.description if scenario else None,
        communication_goal=scenario.communication_goal if scenario else None,
        scenario_context=_scenario_prompt_context(scenario),
        history=history,
        feedback_messages=feedback_messages,
    )
    service = get_room_conversation_service()
    result = (
        service.process_text(request, context)
        if isinstance(request, TextRoomTurnRequest)
        else service.process_voice(request, context)
    )

    turn_limit_reached = _advance_room_turn(
        room, actor, scenario, goal_achieved=result.conversation.goal_achieved
    )
    if turn_limit_reached and scenario and scenario.turn_limit_exit_line:
        result = service.replace_answer(result, scenario.turn_limit_exit_line)

    assistant_message = ChatMessage(
        room_id=room.id, role="assistant", content=result.conversation.answer
    )
    db.add(assistant_message)
    db.flush()
    owner_id = actor.user_id or actor.guest_id or "unknown"
    assistant_message.audio_storage_path = SupabaseMediaStorage().upload_chat_audio(
        Path(result.conversation.audio.audio_path),
        owner_id=owner_id,
        room_id=room.id,
        message_id=assistant_message.id,
    )
    persisted_feedback = result.feedback.model_dump(mode="json")
    persisted_feedback["turn"] = {
        "input_type": result.conversation.input_type,
        "duration_seconds": (
            (request.duration_seconds or 0) if isinstance(request, VoiceRoomTurnRequest) else 0
        ),
        "voice_emotion": (
            result.conversation.voice_emotion.model_dump(mode="json")
            if result.conversation.voice_emotion else None
        ),
    }
    feedback = ChatFeedback(
        room_id=room.id,
        last_message_id=user_message.id,
        model=FEEDBACK_MODEL,
        prompt_version=FEEDBACK_PROMPT_VERSION,
        score=result.feedback.score,
        result_json=persisted_feedback,
    )
    db.add(feedback)
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
    feedback_by_message = {item.last_message_id: item.result_json for item in room.feedbacks}
    messages = []
    for message in room.messages:
        stored = feedback_by_message.get(message.id)
        message_feedback = None
        if stored is not None:
            turn = stored.get("turn", {})
            message_feedback = {
                "input_type": turn.get("input_type", "text"),
                "duration_seconds": turn.get("duration_seconds", 0),
                "score": stored["score"],
                "summary": stored["summary"],
                "improvements": stored.get("improvements", []),
                "voice_emotion": turn.get("voice_emotion"),
            }
        messages.append(_to_message_response(message, feedback=message_feedback))
    return ChatMessageListResponse(messages=messages)


@router.get("/rooms/{room_id}/messages/{message_id}/audio")
def get_message_audio(
    room_id: str,
    message_id: str,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> Response:
    room = _get_room_or_404(db, room_id, actor)
    message = next((item for item in room.messages if item.id == message_id), None)
    if message is None or not message.audio_storage_path:
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다.")
    return Response(
        content=SupabaseMediaStorage().download_chat_audio(message.audio_storage_path),
        media_type="audio/wav",
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="질문을 입력해 주세요.")
    history = [
        {"role": message.role, "content": message.content}
        for message in room.messages[-HISTORY_LIMIT:]
    ]
    user_message = ChatMessage(room_id=room.id, role="user", content=question)
    db.add(user_message)
    db.commit()

    scenario = catalog.find_scenario(db, room.scenario_id) if room.scenario_id else None
    scenario_context = _scenario_prompt_context(scenario)
    response_style = None
    goal_achieved = False
    if request.analysis is not None:
        generation = generate_structured_answer(
            question,
            persona=room.persona_id,
            history=history,
            analysis=request.analysis.model_dump(mode="json"),
            scenario=scenario_context,
        )
        answer = generation.answer
        response_style = generation.response_style
        goal_achieved = generation.goal_achieved
    else:
        answer = generate_answer(
            question,
            persona=room.persona_id,
            history=history,
            scenario=scenario_context,
        )

    assistant_message = ChatMessage(room_id=room.id, role="assistant", content=answer)
    db.add(assistant_message)
    _advance_room_turn(room, actor, scenario, goal_achieved=goal_achieved)
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
        raise HTTPException(
            status_code=403, detail="게스트 대화에는 수동 피드백을 제공하지 않습니다."
        )
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
