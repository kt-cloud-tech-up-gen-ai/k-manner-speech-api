"""페르소나 답변을 TTS로 변환할 때 사용하는 요청·응답 계약."""

from pydantic import BaseModel, Field

class EmotionTtsRequest(BaseModel):
    """페르소나가 결정한 답변 내용과 말투 지시를 담는 요청."""

    text: str = Field(
        min_length=1,
        max_length=4_000,
        description="페르소나가 생성한 최종 답변 텍스트",
        examples=["안녕하세요. 무엇을 도와드릴까요?"],
    )
    speaking_style: str = Field(
        min_length=1,
        max_length=1_000,
        description="페르소나가 지정한 답변 말투·감정·속도 지시",
        examples=["친근하고 밝은 목소리로, 자연스러운 속도로 말한다."],
    )


class EmotionTtsResponse(BaseModel):
    """생성 파일 위치와 재현에 필요한 실제 provider 설정을 담는 응답."""

    text: str
    speaking_style: str
    audio_path: str
    metadata_path: str
    tts_provider: str
    tts_model: str
    voice_name: str


class HealthResponse(BaseModel):
    """라우터 등록 상태를 표현하는 가벼운 상태 확인 응답."""

    status: str
