from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services import catalog, tts

router = APIRouter(tags=["voice"])

# TODO(KAN-64): persona YAML의 voice_id가 아직 전부 비어 있어 실제로는 ELEVENLABS_VOICE_ID
#   기본 음성만 쓰인다. persona별 ElevenLabs 음성 ID를 채워 넣을 것.
#   → app/prompts/bundles/personas/*.yaml
# TODO(KAN-64): ElevenLabs 실계정으로 엔드투엔드 검증이 필요하다. 현재 테스트는 urlopen을 목킹한다.


class TtsRequest(BaseModel):
    text: str = Field(min_length=1)
    persona_id: str | None = Field(default=None, max_length=64)


class TtsResponse(BaseModel):
    audio: str
    mimeType: str
    voice_id: str


def resolve_voice_id(persona_id: str | None) -> str:
    """persona YAML의 voice_id → 환경변수 기본값 순으로 음성을 고른다."""
    if persona_id:
        persona = catalog.find_persona(persona_id)
        if persona is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"알 수 없는 persona입니다: {persona_id}",
            )
        if persona.voice_id:
            return persona.voice_id

    default_voice = tts.get_default_voice_id()
    if not default_voice:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="사용할 TTS 음성이 설정되지 않았습니다.",
        )
    return default_voice


@router.post("/tts", response_model=TtsResponse)
def text_to_speech(request: TtsRequest) -> TtsResponse:
    """텍스트를 ElevenLabs 음성으로 합성해 base64로 반환한다. (KAN-64)"""
    voice_id = resolve_voice_id(request.persona_id)
    audio = tts.synthesize(request.text, voice_id)
    return TtsResponse(audio=audio, mimeType=tts.OUTPUT_MIME_TYPE, voice_id=voice_id)
