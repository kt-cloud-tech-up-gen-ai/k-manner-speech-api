import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.emotion_group import Emotion


class GeminiUserTextAnalyzerTests(unittest.TestCase):
    def _service(self, parsed):
        from app.services.gemini_user_text_analyzer import GeminiUserTextAnalyzer

        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(parsed=parsed)
        return GeminiUserTextAnalyzer(client, "gemini-analysis"), client

    def test_returns_public_analysis_from_one_gemini_call(self):
        service, client = self._service(
            {
                "emotion": "보통",
                "inferred_style": " 차분한 말투 ",
                "intent": " 인사 ",
            }
        )

        result = service.analyze_text("  안녕하세요  ")

        self.assertEqual(result.user_text, "안녕하세요")
        self.assertEqual(result.user_emotion, Emotion.NORMAL)
        self.assertEqual(result.inferred_style, "차분한 말투")
        self.assertEqual(result.user_intent, "인사")
        client.models.generate_content.assert_called_once()

    def test_blank_text_stops_before_gemini_call(self):
        service, client = self._service({})

        with self.assertRaisesRegex(ValueError, "텍스트를 입력하세요"):
            service.analyze_text("   ")

        client.models.generate_content.assert_not_called()

    def test_missing_parsed_response_raises_runtime_error(self):
        service, _ = self._service(None)

        with self.assertRaisesRegex(RuntimeError, "응답을 해석하지 못했습니다"):
            service.analyze_text("안녕하세요")


if __name__ == "__main__":
    unittest.main()
