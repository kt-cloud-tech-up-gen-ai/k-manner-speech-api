"""Room 문맥에서 음성·텍스트 대화와 피드백을 결합하는 계약."""

from pydantic import BaseModel, Field

from app.schemas.conversation import ConversationResponse
from app.schemas.rooms import ChatMessageResponse
from app.schemas.voice_emotion import OptionalVoiceEmotionAnalysisRequest
from app.services.feedback import FeedbackMessage, FeedbackResult


class TextRoomTurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)


class VoiceRoomTurnRequest(OptionalVoiceEmotionAnalysisRequest):
    pass


class RoomConversationContext(BaseModel):
    """DB에서 조회해 AI 서비스에 전달하는 신뢰 가능한 Room 문맥."""

    room_id: str
    user_id: str
    persona_id: str
    persona_description: str
    scenario_description: str | None
    communication_goal: str | None
    scenario_context: dict[str, object] | None = None
    history: list[dict[str, str]]
    feedback_messages: list[FeedbackMessage]


class RoomConversationResult(BaseModel):
    conversation: ConversationResponse
    feedback: FeedbackResult


class RoomTurnResponse(RoomConversationResult):
    room_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
