"""Gemini 분석 결과를 공개 API 응답으로 조립합니다."""

from app.schemas.user_input import UserInputAnalysis
from app.services.user_input_Text import EmotionClassifierService


class UserInputPipelineService:
    def __init__(self, text_analyzer: EmotionClassifierService) -> None:
        self.text_analyzer = text_analyzer

    def analyze_text(self, text: str) -> UserInputAnalysis:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("텍스트를 입력하세요.")
        analysis = self.text_analyzer.analyze_text(clean_text)
        return UserInputAnalysis(
            user_text=clean_text,
            user_emotion=analysis.emotion,
            user_speaking_style=None,
            inferred_style=analysis.inferred_style.strip(),
            user_intent=analysis.intent.strip(),
        )
