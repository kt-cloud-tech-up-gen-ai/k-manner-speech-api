import base64
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


class GeminiVoiceEmotionAnalyzerTests(unittest.TestCase):
    def _service(self, parsed):
        from app.services.gemini_voice_emotion_analyzer import GeminiVoiceEmotionAnalyzer

        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(parsed=parsed)
        return GeminiVoiceEmotionAnalyzer(client, "gemini-3.6-flash"), client

    def test_analyzes_inline_audio_and_normalizes_percentages(self):
        service, client = self._service(
            {
                "emotions": [
                    {"label": "차분함", "percentage": 71},
                    {"label": "친절함", "percentage": 18},
                    {"label": "긴장감", "percentage": 10},
                ],
                "impressions": ["차분하게 들려요", "공손한 말투예요"],
            }
        )

        result = service.analyze(
            audio_bytes=b"RIFF-audio",
            mime_type="audio/wav",
            transcript="실례합니다, 혹시 공대 건물이 어디예요?",
        )

        self.assertEqual(sum(item.percentage for item in result.emotions), 100)
        self.assertEqual(result.emotions[0].label, "차분함")
        self.assertEqual(result.impressions, ["차분하게 들려요", "공손한 말투예요"])
        self.assertEqual(result.model, "gemini-3.6-flash")
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-3.6-flash")
        self.assertEqual(len(kwargs["contents"]), 2)

    def test_rejects_blank_audio_before_provider_call(self):
        service, client = self._service({})

        with self.assertRaisesRegex(ValueError, "음성 데이터"):
            service.analyze(audio_bytes=b"", mime_type="audio/wav", transcript="안녕하세요")

        client.models.generate_content.assert_not_called()

    def test_rejects_unsupported_mime_before_provider_call(self):
        service, client = self._service({})

        with self.assertRaisesRegex(ValueError, "지원하지 않는 음성 형식"):
            service.analyze(audio_bytes=b"audio", mime_type="video/mp4", transcript="안녕하세요")

        client.models.generate_content.assert_not_called()

    def test_missing_structured_response_does_not_fabricate_feedback(self):
        service, _ = self._service(None)

        with self.assertRaisesRegex(RuntimeError, "음성 감정 분석 응답"):
            service.analyze(
                audio_bytes=b"RIFF-audio",
                mime_type="audio/wav",
                transcript="안녕하세요",
            )


class VoiceEmotionRequestTests(unittest.TestCase):
    def test_decodes_valid_base64_audio(self):
        from app.schemas.voice_emotion import VoiceEmotionAnalysisRequest

        request = VoiceEmotionAnalysisRequest(
            transcript="안녕하세요",
            audio_base64=base64.b64encode(b"RIFF-audio").decode(),
            audio_mime_type="audio/wav",
        )

        self.assertEqual(request.audio_bytes(), b"RIFF-audio")

    def test_invalid_base64_is_rejected(self):
        from pydantic import ValidationError

        from app.schemas.voice_emotion import VoiceEmotionAnalysisRequest

        with self.assertRaises(ValidationError):
            VoiceEmotionAnalysisRequest(
                transcript="안녕하세요",
                audio_base64="not@@base64",
                audio_mime_type="audio/wav",
            )

    def test_optional_room_audio_fields_must_be_supplied_together(self):
        from pydantic import ValidationError

        from app.schemas.room_conversation import VoiceRoomTurnRequest

        with self.assertRaisesRegex(ValidationError, "함께 입력"):
            VoiceRoomTurnRequest(
                transcript="안녕하세요",
                audio_base64=base64.b64encode(b"RIFF-audio").decode(),
            )


class VoiceEmotionEndpointTests(unittest.TestCase):
    def test_endpoint_returns_structured_voice_feedback(self):
        from app.main import app
        from app.schemas.voice_emotion import EmotionScore, VoiceEmotionAnalysis

        analyzer = Mock()
        analyzer.analyze.return_value = VoiceEmotionAnalysis(
            transcript="안녕하세요",
            emotions=[
                EmotionScore(label="차분함", percentage=70),
                EmotionScore(label="친절함", percentage=20),
                EmotionScore(label="긴장감", percentage=10),
            ],
            impressions=["차분하게 들려요"],
            model="gemini-3.6-flash",
        )
        with (
            patch.dict(
                "os.environ",
                {"GUEST_SESSION_SECRET": "test-secret-32-bytes-minimum-value"},
            ),
            patch(
                "app.routers.room_conversation.get_voice_emotion_analyzer",
                return_value=analyzer,
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                "/voice/emotion-analysis",
                json={
                    "transcript": "안녕하세요",
                    "audio_base64": base64.b64encode(b"RIFF-audio").decode(),
                    "audio_mime_type": "audio/wav",
                    "duration_seconds": 1.2,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["emotions"][0]["label"], "차분함")
        analyzer.analyze.assert_called_once()

    def test_endpoint_rejects_unsupported_audio_without_model_call(self):
        from app.main import app

        analyzer = Mock()
        with (
            patch.dict(
                "os.environ",
                {"GUEST_SESSION_SECRET": "test-secret-32-bytes-minimum-value"},
            ),
            patch(
                "app.routers.room_conversation.get_voice_emotion_analyzer",
                return_value=analyzer,
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                "/voice/emotion-analysis",
                json={
                    "transcript": "안녕하세요",
                    "audio_base64": base64.b64encode(b"video").decode(),
                    "audio_mime_type": "video/mp4",
                },
            )

        self.assertEqual(response.status_code, 422)
        analyzer.analyze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
