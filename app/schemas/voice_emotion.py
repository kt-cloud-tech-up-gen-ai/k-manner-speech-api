"""Gemini 음성 감정 분석의 입력·출력 계약."""

import base64
import binascii

from pydantic import BaseModel, Field, field_validator

MAX_AUDIO_BYTES = 20 * 1024 * 1024
SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/aac",
    "audio/aiff",
    "audio/flac",
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-wav",
}


class VoiceEmotionAnalysisRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4_000)
    audio_base64: str = Field(min_length=1, max_length=28_000_000)
    audio_mime_type: str = Field(min_length=1, max_length=100)
    duration_seconds: float | None = Field(default=None, gt=0, le=600)

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("음성 인식 텍스트를 입력하세요.")
        return clean_value

    @field_validator("audio_mime_type")
    @classmethod
    def validate_audio_mime_type(cls, value: str) -> str:
        clean_value = value.split(";", 1)[0].strip().lower()
        if clean_value not in SUPPORTED_AUDIO_MIME_TYPES:
            raise ValueError(f"지원하지 않는 음성 형식입니다: {clean_value}")
        return clean_value

    @field_validator("audio_base64")
    @classmethod
    def validate_audio_base64(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("audio_base64는 올바른 Base64여야 합니다.") from exc
        if not decoded:
            raise ValueError("음성 데이터가 비어 있습니다.")
        if len(decoded) > MAX_AUDIO_BYTES:
            raise ValueError("음성 데이터는 20MB 이하여야 합니다.")
        return value

    def audio_bytes(self) -> bytes:
        return base64.b64decode(self.audio_base64, validate=True)


class EmotionScore(BaseModel):
    label: str = Field(min_length=1, max_length=30)
    percentage: int = Field(ge=0, le=100)


class VoiceEmotionModelAnalysis(BaseModel):
    emotions: list[EmotionScore] = Field(min_length=3, max_length=3)
    impressions: list[str] = Field(min_length=1, max_length=3)


class VoiceEmotionAnalysis(VoiceEmotionModelAnalysis):
    transcript: str
    model: str
