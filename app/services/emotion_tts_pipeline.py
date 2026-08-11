"""감정·말투 조립, Gemini TTS 호출, 결과 파일 저장을 조정합니다."""

import json
from datetime import datetime

from app.core.config import TtsSettings
from app.schemas.emotion_tts import EmotionTtsRequest, EmotionTtsResponse
from app.services.tts import GeminiTtsService


class EmotionTtsService:
    """스타일 결정부터 Gemini 호출, WAV·JSON 저장까지 조정합니다."""

    def __init__(self, settings: TtsSettings) -> None:
        """상위 설정을 저수준 Gemini TTS 어댑터에 주입합니다."""

        self.settings = settings
        self.tts = GeminiTtsService(settings.google_api_key, settings.tts_model)

    def generate(self, request: EmotionTtsRequest) -> EmotionTtsResponse:
        """요청을 음성으로 합성하고 추적 가능한 파일 두 개를 생성합니다."""

        text = request.text.strip()
        # 페르소나 서비스가 결정한 말투를 추가 해석 없이 Gemini에 전달합니다.
        speaking_style = request.speaking_style.strip()
        voice_name = self.settings.voice_name
        # 이 호출에서만 외부 네트워크 요청과 Gemini API 사용량이 발생합니다.
        audio = self.tts.synthesize(text, speaking_style, voice_name)

        # 마이크로초를 포함해 동시 요청 간 파일명 충돌을 줄입니다.
        stem = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        audio_path = self.settings.output_dir / f"{stem}.wav"
        metadata_path = self.settings.output_dir / f"{stem}.json"
        self.tts.write_wav(audio_path, audio)
        # 응답에 실제 모델과 Gemini 음성 이름을 기록해 결과를 나중에 재현할 수 있게 합니다.
        result = EmotionTtsResponse(
            text=text,
            speaking_style=speaking_style,
            audio_path=str(audio_path.resolve()),
            metadata_path=str(metadata_path.resolve()),
            tts_provider="gemini",
            tts_model=self.settings.tts_model,
            voice_name=voice_name,
        )
        # WAV와 같은 stem의 JSON 메타데이터를 남겨 청취 평가와 연결합니다.
        metadata_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
