"""STT 결과부터 Gemini TTS까지 연결하는 통합 API 계약."""

from pydantic import BaseModel, Field

from app.schemas.emotion_tts import EmotionTtsResponse
from app.schemas.user_input import UserInputAnalysis


class SpeechPipelineRequest(BaseModel):
    """STT가 추출한 텍스트와 답변에 사용할 페르소나."""

    text: str = Field(
        min_length=1,
        max_length=4_000,
        description="STT가 음성에서 추출한 최종 텍스트",
        examples=["오늘 정말 기분 좋은 일이 있었어."],
    )
    persona: str = Field(
        min_length=1,
        max_length=100,
        description="채팅 답변에 적용할 페르소나 이름",
        examples=["friendly"],
    )


class SpeechPipelineResponse(BaseModel):
    """분석·채팅·TTS 각 단계의 결과."""

    source_text: str
    persona: str
    analysis: UserInputAnalysis
    answer: str
    response_style: str
    audio: EmotionTtsResponse
    processing_time_ms: float = Field(ge=0)
