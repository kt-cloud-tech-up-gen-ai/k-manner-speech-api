"""Gemini TTS로 페르소나 답변을 WAV 음성으로 생성한다."""

import json
import wave
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types

from app.core.config import TtsSettings
from app.schemas.emotion_tts import EmotionTtsRequest, EmotionTtsResponse

PCM_SAMPLE_RATE = 24_000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2


class GeminiAnswerAudioGenerator:
    """답변과 답변 말투를 Gemini에 전달하고 WAV·메타데이터를 저장한다."""

    def __init__(self, settings: TtsSettings) -> None:
        self.settings = settings
        self.client = genai.Client(api_key=settings.google_api_key)

    def generate(self, request: EmotionTtsRequest) -> EmotionTtsResponse:
        text = request.text.strip()
        speaking_style = request.speaking_style.strip()
        voice_name = self.settings.voice_name
        audio = self._synthesize(text, speaking_style, voice_name)

        stem = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        audio_path = self.settings.output_dir / f"{stem}.wav"
        metadata_path = self.settings.output_dir / f"{stem}.json"
        self._write_wav(audio_path, audio)
        result = EmotionTtsResponse(
            text=text,
            speaking_style=speaking_style,
            audio_path=str(audio_path.resolve()),
            metadata_path=str(metadata_path.resolve()),
            tts_provider="gemini",
            tts_model=self.settings.tts_model,
            voice_name=voice_name,
        )
        metadata_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result

    def _synthesize(self, text: str, style: str, voice_name: str) -> bytes:
        prompt = (
            "다음 지시에 따라 음성을 합성하세요. 지시문 자체는 읽지 말고, "
            "[읽을 원문]의 내용만 정확히 한국어로 발화하세요.\n\n"
            f"[연기 지시]\n{style.strip()}\n\n[읽을 원문]\n{text.strip()}"
        )
        response = self.client.models.generate_content(
            model=self.settings.tts_model,
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
    def _write_wav(path: Path, pcm: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(PCM_CHANNELS)
            wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
            wav_file.setframerate(PCM_SAMPLE_RATE)
            wav_file.writeframes(pcm)
