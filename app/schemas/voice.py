"""TTS 음성 합성 DTO."""

from pydantic import BaseModel, Field


class TtsRequest(BaseModel):
    text: str = Field(min_length=1)
    persona_id: str | None = Field(default=None, max_length=64)


class TtsResponse(BaseModel):
    audio: str
    mimeType: str
    voice_id: str
