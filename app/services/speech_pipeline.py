"""STT 텍스트 분석, 채팅 답변, Gemini TTS를 순서대로 조정한다."""

from collections.abc import Callable
from time import perf_counter
from typing import Protocol

from app.schemas.emotion_tts import EmotionTtsRequest, EmotionTtsResponse
from app.schemas.speech_pipeline import SpeechPipelineRequest, SpeechPipelineResponse
from app.schemas.user_input import UserInputAnalysis
from app.services.llm import ChatGeneration


class TextAnalyzer(Protocol):
    def analyze_text(self, text: str) -> UserInputAnalysis: ...


class TtsGenerator(Protocol):
    def generate(self, request: EmotionTtsRequest) -> EmotionTtsResponse: ...


ChatGenerator = Callable[..., ChatGeneration]


class SpeechPipelineService:
    """각 기존 서비스를 한 번씩 호출해 음성 대화 결과를 만든다."""

    def __init__(
        self,
        analyzer: TextAnalyzer,
        chat_generator: ChatGenerator,
        tts_service: TtsGenerator,
    ) -> None:
        self.analyzer = analyzer
        self.chat_generator = chat_generator
        self.tts_service = tts_service

    def generate(self, request: SpeechPipelineRequest) -> SpeechPipelineResponse:
        started_at = perf_counter()
        text = request.text.strip()
        persona = request.persona.strip()
        if not text:
            raise ValueError("STT로 추출한 텍스트를 입력하세요.")
        if not persona:
            raise ValueError("답변에 사용할 페르소나를 입력하세요.")

        analysis = self.analyzer.analyze_text(text)
        chat_result = self.chat_generator(
            text,
            persona=persona,
            analysis={
                "emotion": analysis.user_emotion.value,
                "inferred_style": analysis.inferred_style or "",
                "intent": analysis.user_intent,
            },
        )
        answer = chat_result.answer.strip()
        response_style = (chat_result.response_style or "").strip()
        if not answer:
            raise RuntimeError("채팅 Gemini가 답변을 반환하지 않았습니다.")
        if not response_style:
            raise RuntimeError("채팅 Gemini가 답변 말투를 반환하지 않았습니다.")

        audio = self.tts_service.generate(
            EmotionTtsRequest(text=answer, speaking_style=response_style)
        )
        return SpeechPipelineResponse(
            source_text=text,
            persona=persona,
            analysis=analysis,
            answer=answer,
            response_style=response_style,
            audio=audio,
            processing_time_ms=round((perf_counter() - started_at) * 1_000, 2),
        )
