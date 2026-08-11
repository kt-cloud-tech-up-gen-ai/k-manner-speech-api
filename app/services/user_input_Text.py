"""Gemini로 텍스트의 감정·표현 방식·의도를 분석합니다."""

from google import genai
from google.genai import types

from app.schemas.user_input import TextModelAnalysis

TEXT_ANALYSIS_PROMPT = """당신은 한국어 텍스트 입력 분석기입니다.
텍스트의 의미, 어미, 감탄사, 문장부호를 바탕으로 감정과 의도를 추론하세요.

규칙:
- emotion은 화남, 기쁨, 당황스러움, 궁금, 슬픔, 보통 중 하나입니다.
- 음성이 없으므로 실제 말투를 관찰했다고 주장하지 마세요. inferred_style은 텍스트로 추론한 표현 방식입니다.
- 응답은 emotion, inferred_style, intent 세 필드만 간결하게 생성합니다.

분석할 텍스트:
{text}
"""


class EmotionClassifierService:
    def __init__(self, client: genai.Client, model: str) -> None:
        self.client = client
        self.model = model

    def analyze_text(self, text: str) -> TextModelAnalysis:
        response = self.client.models.generate_content(
            model=self.model,
            contents=TEXT_ANALYSIS_PROMPT.format(text=text.strip()),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TextModelAnalysis,
            ),
        )
        if response.parsed is None:
            raise RuntimeError("텍스트 입력 분석 응답을 해석하지 못했습니다.")
        return TextModelAnalysis.model_validate(response.parsed)
