"""입력 분석, 페르소나 답변, Gemini TTS를 순서대로 실행한다."""

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Literal, Protocol

from app.schemas.conversation import (
    ConversationResponse,
    TextConversationRequest,
    VoiceConversationRequest,
)
from app.schemas.emotion_tts import EmotionTtsRequest, EmotionTtsResponse
from app.schemas.user_input import UserInputAnalysis
from app.services.llm import ChatGeneration


class TextAnalyzer(Protocol):
    def analyze_text(self, text: str) -> UserInputAnalysis: ...


class TtsGenerator(Protocol):
    def generate(self, request: EmotionTtsRequest) -> EmotionTtsResponse: ...


ChatGenerator = Callable[..., ChatGeneration]


class ConversationPipelineService:
    """음성·텍스트 입력에 동일한 3단계 페르소나 대화 흐름을 적용한다."""

    def __init__(
        self,
        analyzer: TextAnalyzer,
        chat_generator: ChatGenerator,
        tts_service: TtsGenerator,
    ) -> None:
        self.analyzer = analyzer
        self.chat_generator = chat_generator
        self.tts_service = tts_service

    def process_voice(
        self,
        request: VoiceConversationRequest,
        *,
        history: list[dict[str, str]] | None = None,
        scenario: Mapping[str, object] | None = None,
    ) -> ConversationResponse:
        return self._process(
            "voice",
            request.transcript,
            request.persona,
            history=history,
            scenario=scenario,
        )

    def process_text(
        self,
        request: TextConversationRequest,
        *,
        history: list[dict[str, str]] | None = None,
        scenario: Mapping[str, object] | None = None,
    ) -> ConversationResponse:
        return self._process(
            "text",
            request.text,
            request.persona,
            history=history,
            scenario=scenario,
        )

    def _process(
        self,
        input_type: Literal["voice", "text"],
        text: str,
        persona: str,
        *,
        history: list[dict[str, str]] | None,
        scenario: Mapping[str, object] | None,
    ) -> ConversationResponse:
        started_at = perf_counter()
        clean_text = text.strip()
        clean_persona = persona.strip()
        if not clean_text:
            raise ValueError("처리할 텍스트를 입력하세요.")
        if not clean_persona:
            raise ValueError("답변에 사용할 페르소나를 입력하세요.")

        analysis = self.analyzer.analyze_text(clean_text)
        chat_result = self.chat_generator(
            clean_text,
            persona=clean_persona,
            analysis={
                "emotion": analysis.user_emotion.value,
                "inferred_style": analysis.inferred_style or "",
                "intent": analysis.user_intent,
            },
            history=history,
            scenario=scenario,
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
        return ConversationResponse(
            input_type=input_type,
            source_text=clean_text,
            persona=clean_persona,
            analysis=analysis,
            answer=answer,
            goal_achieved=chat_result.goal_achieved,
            response_style=response_style,
            audio=audio,
            processing_time_ms=round((perf_counter() - started_at) * 1_000, 2),
        )
