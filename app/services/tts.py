"""ElevenLabs Text-to-Speech 연동."""

import base64
import json
import logging
import os
import wave
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import HTTPException, status
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

ELEVENLABS_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
OUTPUT_MIME_TYPE = "audio/mpeg"
PCM_SAMPLE_RATE = 24_000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2


class GeminiTtsService:
    """Gemini 호출과 24kHz PCM의 WAV 저장을 담당하는 어댑터."""

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = genai.Client(api_key=api_key)

    def synthesize(self, text: str, style: str, voice_name: str) -> bytes:
        """페르소나의 말투 지시와 답변을 Gemini TTS 음성으로 변환한다."""

        prompt = (
            "다음 지시에 따라 음성을 합성하세요. 지시문 자체는 읽지 말고, "
            "[읽을 원문]의 내용만 정확히 한국어로 발화하세요.\n\n"
            f"[연기 지시]\n{style.strip()}\n\n[읽을 원문]\n{text.strip()}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            ),
        )
        try:
            audio = response.candidates[0].content.parts[0].inline_data.data
        except (AttributeError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini TTS 응답에 오디오 데이터가 없습니다.") from error
        if not audio:
            raise RuntimeError("Gemini TTS 응답에 오디오 데이터가 없습니다.")
        return audio

    @staticmethod
    def write_wav(path: Path, pcm: bytes) -> None:
        """24kHz mono 16-bit PCM을 표준 WAV 컨테이너로 저장한다."""

        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(PCM_CHANNELS)
            wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
            wav_file.setframerate(PCM_SAMPLE_RATE)
            wav_file.writeframes(pcm)


def get_api_key() -> str | None:
    return os.getenv("ELEVENLABS_API_KEY")


def get_default_voice_id() -> str | None:
    return os.getenv("ELEVENLABS_VOICE_ID")


def get_model_id() -> str:
    return os.getenv("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL_ID


def synthesize(text: str, voice_id: str) -> str:
    """텍스트를 음성으로 합성하고 base64 문자열을 반환한다."""
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS API가 구성되지 않았습니다.",
        )

    payload = {"text": text, "model_id": get_model_id()}
    request = UrlRequest(
        f"{ELEVENLABS_ENDPOINT}/{quote(voice_id, safe='')}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": OUTPUT_MIME_TYPE,
            "xi-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            audio = response.read()
    except HTTPError as exc:
        body = _read_error_body(exc)
        logger.warning("ElevenLabs returned HTTP %s: %s", exc.code, body or "<empty>")
        client_status = 400 if 400 <= exc.code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail=f"TTS 요청이 거부되었습니다. (upstream HTTP {exc.code})",
        ) from exc
    except TimeoutError as exc:
        logger.exception("ElevenLabs request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="TTS 응답 시간이 초과되었습니다.",
        ) from exc
    except URLError as exc:
        logger.exception("Could not connect to ElevenLabs")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS 서비스에 연결하지 못했습니다.",
        ) from exc
    except OSError as exc:
        logger.exception("Could not read ElevenLabs response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS 응답을 처리하지 못했습니다.",
        ) from exc

    if not audio:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS 응답에 오디오가 없습니다.",
        )

    return base64.b64encode(audio).decode("ascii")


def _read_error_body(exc: HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:4096]
    except OSError:
        return "<failed to read response body>"
