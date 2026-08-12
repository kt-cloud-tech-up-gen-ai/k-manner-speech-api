"""무상태 채팅(`/chat`)과 Gemini 원본 호출(`/ask_gemini`)의 DTO."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user_input import TextModelAnalysis


class ChatRequest(BaseModel):
    persona: str
    question: str
    analysis: TextModelAnalysis | None = None


class ChatResponse(BaseModel):
    answer: str
    response_style: str | None = None


class GenerationConfig(BaseModel):
    """Gemini generateContent의 생성 설정."""

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    topP: float | None = Field(default=None, ge=0.0, le=1.0)
    topK: int | None = Field(default=None, ge=1)
    maxOutputTokens: int | None = Field(default=None, ge=1)
    candidateCount: int | None = Field(default=None, ge=1)
    stopSequences: list[str] | None = None
    responseMimeType: str | None = None


class AskGeminiRequest(BaseModel):
    systemInstruction: str
    contents: str
    generationConfig: GenerationConfig | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "systemInstruction": "당신의 이름은 도윤이고, 대학선배입니다. 한국어로 친절하게 답변하세요.",
                "contents": "선배님 안녕하세요",
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1000,
                },
            }
        }
    }
