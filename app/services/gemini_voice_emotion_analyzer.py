"""Gemini 3.6 Flash로 녹음 음성의 감정과 상대 인상을 분석한다."""

from google import genai
from google.genai import types

from app.schemas.voice_emotion import (
    SUPPORTED_AUDIO_MIME_TYPES,
    EmotionScore,
    VoiceEmotionAnalysis,
    VoiceEmotionModelAnalysis,
)

VOICE_EMOTION_PROMPT = """당신은 한국어 말하기 코치입니다.
첨부된 실제 음성의 톤, 속도, 강세, 머뭇거림을 듣고 화자의 감정을 분석하세요.
STT 참고 문장은 내용 확인용이며, 음향적으로 관찰되지 않은 감정을 단정하지 마세요.

규칙:
- 가장 두드러진 감정/말투 특성 3개를 짧은 한국어 명사형 label로 작성합니다.
- percentage 세 값의 합은 100이 되게 합니다.
- impressions에는 상대방이 받을 법한 인상을 존중하는 한국어 문장 1~3개로 작성합니다.
- 성격, 정신건강, 거짓말 여부처럼 음성만으로 알 수 없는 특성은 추론하지 않습니다.

STT 참고 문장:
{transcript}
"""


class GeminiVoiceEmotionAnalyzer:
    def __init__(self, client: genai.Client, model: str) -> None:
        self.client = client
        self.model = model

    def analyze(
        self, *, audio_bytes: bytes, mime_type: str, transcript: str
    ) -> VoiceEmotionAnalysis:
        clean_transcript = transcript.strip()
        clean_mime = mime_type.split(";", 1)[0].strip().lower()
        if not audio_bytes:
            raise ValueError("음성 데이터를 입력하세요.")
        if not clean_transcript:
            raise ValueError("음성 인식 텍스트를 입력하세요.")
        if clean_mime not in SUPPORTED_AUDIO_MIME_TYPES:
            raise ValueError(f"지원하지 않는 음성 형식입니다: {clean_mime}")

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                VOICE_EMOTION_PROMPT.format(transcript=clean_transcript),
                types.Part.from_bytes(data=audio_bytes, mime_type=clean_mime),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VoiceEmotionModelAnalysis,
            ),
        )
        if response.parsed is None:
            raise RuntimeError("Gemini 음성 감정 분석 응답을 해석하지 못했습니다.")

        parsed = VoiceEmotionModelAnalysis.model_validate(response.parsed)
        emotions = self._normalize_percentages(parsed.emotions)
        impressions = [item.strip() for item in parsed.impressions if item.strip()]
        if not impressions:
            raise RuntimeError("Gemini 음성 감정 분석 응답에 인상 피드백이 없습니다.")
        return VoiceEmotionAnalysis(
            transcript=clean_transcript,
            emotions=emotions,
            impressions=impressions,
            model=self.model,
        )

    @staticmethod
    def _normalize_percentages(emotions: list[EmotionScore]) -> list[EmotionScore]:
        total = sum(item.percentage for item in emotions)
        if total <= 0:
            raise RuntimeError("Gemini 음성 감정 분석 비율이 올바르지 않습니다.")
        normalized = [round(item.percentage * 100 / total) for item in emotions]
        normalized[-1] += 100 - sum(normalized)
        return [
            EmotionScore(label=item.label.strip(), percentage=percentage)
            for item, percentage in zip(emotions, normalized, strict=True)
        ]
