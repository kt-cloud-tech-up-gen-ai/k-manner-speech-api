"""음성·텍스트 기반 페르소나 대화 API 계약."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.emotion_tts import EmotionTtsResponse
from app.schemas.user_input import UserInputAnalysis
from app.schemas.voice_emotion import (
    OptionalVoiceEmotionAnalysisRequest,
    VoiceEmotionAnalysis,
)


class VoiceConversationRequest(OptionalVoiceEmotionAnalysisRequest):
    """브라우저 STT가 확정한 음성 입력 텍스트."""

    persona: str = Field(min_length=1, max_length=100)


class TextConversationRequest(BaseModel):
    """사용자가 직접 작성한 텍스트 입력."""

    text: str = Field(min_length=1, max_length=4_000)
    persona: str = Field(min_length=1, max_length=100)


class ConversationResponse(BaseModel):
    """분석·페르소나 답변·TTS를 모두 포함하는 통합 응답."""

    input_type: Literal["voice", "text"]
    source_text: str
    goal_achieved: bool = False
    persona: str
    analysis: UserInputAnalysis
    voice_emotion: VoiceEmotionAnalysis | None = None
    answer: str
    response_style: str
    audio: EmotionTtsResponse
    processing_time_ms: float = Field(ge=0)
