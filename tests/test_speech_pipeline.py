import importlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.emotion_group import Emotion
from app.schemas.emotion_tts import EmotionTtsResponse
from app.schemas.user_input import UserInputAnalysis


class SpeechPipelineTests(unittest.TestCase):
    def _pipeline_types(self):
        service_module = importlib.import_module("app.services.speech_pipeline")
        schema_module = importlib.import_module("app.schemas.speech_pipeline")
        return service_module.SpeechPipelineService, schema_module.SpeechPipelineRequest

    def test_analysis_chat_and_tts_are_connected_in_order(self):
        SpeechPipelineService, SpeechPipelineRequest = self._pipeline_types()
        analysis = UserInputAnalysis(
            user_text="오늘 정말 기분 좋아!",
            user_emotion=Emotion.HAPPY,
            user_speaking_style=None,
            inferred_style="밝고 들뜬 말투",
            user_intent="기쁜 감정 공유",
        )
        analyzer = Mock()
        analyzer.analyze_text.return_value = analysis
        chat_generator = Mock(
            return_value=SimpleNamespace(
                answer="나도 정말 기뻐!",
                response_style="친근하고 밝은 목소리로 경쾌하게 말한다.",
            )
        )
        tts_result = EmotionTtsResponse(
            text="나도 정말 기뻐!",
            speaking_style="친근하고 밝은 목소리로 경쾌하게 말한다.",
            audio_path=str(Path("app/outputs/result.wav").resolve()),
            metadata_path=str(Path("app/outputs/result.json").resolve()),
            tts_provider="gemini",
            tts_model="gemini-3.1-flash-tts-preview",
            voice_name="Kore",
        )
        tts_service = Mock()
        tts_service.generate.return_value = tts_result
        service = SpeechPipelineService(analyzer, chat_generator, tts_service)

        result = service.generate(
            SpeechPipelineRequest(text="오늘 정말 기분 좋아!", persona="friendly")
        )

        analyzer.analyze_text.assert_called_once_with("오늘 정말 기분 좋아!")
        chat_generator.assert_called_once_with(
            "오늘 정말 기분 좋아!",
            persona="friendly",
            analysis={
                "emotion": "기쁨",
                "inferred_style": "밝고 들뜬 말투",
                "intent": "기쁜 감정 공유",
            },
        )
        tts_request = tts_service.generate.call_args.args[0]
        self.assertEqual(tts_request.text, "나도 정말 기뻐!")
        self.assertEqual(
            tts_request.speaking_style,
            "친근하고 밝은 목소리로 경쾌하게 말한다.",
        )
        self.assertEqual(result.analysis, analysis)
        self.assertEqual(result.answer, "나도 정말 기뻐!")
        self.assertEqual(result.audio, tts_result)

    def test_blank_stt_text_stops_before_external_calls(self):
        SpeechPipelineService, SpeechPipelineRequest = self._pipeline_types()
        analyzer = Mock()
        chat_generator = Mock()
        tts_service = Mock()
        service = SpeechPipelineService(analyzer, chat_generator, tts_service)

        with self.assertRaisesRegex(ValueError, "텍스트"):
            service.generate(SpeechPipelineRequest(text="   ", persona="friendly"))

        analyzer.analyze_text.assert_not_called()
        chat_generator.assert_not_called()
        tts_service.generate.assert_not_called()

    def test_missing_response_style_stops_before_tts(self):
        SpeechPipelineService, SpeechPipelineRequest = self._pipeline_types()
        analyzer = Mock()
        analyzer.analyze_text.return_value = UserInputAnalysis(
            user_text="안녕",
            user_emotion=Emotion.NORMAL,
            user_speaking_style=None,
            inferred_style="평범한 말투",
            user_intent="인사",
        )
        chat_generator = Mock(
            return_value=SimpleNamespace(answer="안녕하세요", response_style=None)
        )
        tts_service = Mock()
        service = SpeechPipelineService(analyzer, chat_generator, tts_service)

        with self.assertRaisesRegex(RuntimeError, "말투"):
            service.generate(SpeechPipelineRequest(text="안녕", persona="friendly"))

        tts_service.generate.assert_not_called()

    def test_openapi_exposes_pipeline_with_text_and_persona(self):
        import app.main

        schema = app.main.app.openapi()
        self.assertIn("/api/v1/speech-pipeline/generate", schema["paths"])
        request_schema = schema["components"]["schemas"]["SpeechPipelineRequest"]
        self.assertEqual(set(request_schema["properties"]), {"text", "persona"})
        self.assertEqual(set(request_schema["required"]), {"text", "persona"})


if __name__ == "__main__":
    unittest.main()
