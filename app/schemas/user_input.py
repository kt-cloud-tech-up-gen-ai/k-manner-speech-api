"""텍스트 감정 분석의 외부 API와 Gemini 구조화 출력 계약."""

from pydantic import BaseModel, Field

from app.schemas.emotion_group import Emotion


class TextUserInputRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)


class UserInputAnalysis(BaseModel):
    user_text: str
    user_emotion: Emotion
    user_speaking_style: str | None = Field(
        description="음향 분석으로 관찰한 말투. 현재 텍스트 기반 분석에서는 null"
    )
    inferred_style: str | None = Field(
        default=None, description="텍스트 표현과 맥락으로 추론한 말투"
    )
    user_intent: str
    processing_time_ms: float | None = Field(default=None, ge=0)


class TextModelAnalysis(BaseModel):
    emotion: Emotion
    inferred_style: str
    intent: str
