import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.emotion_group import Emotion
from app.schemas.emotion_tts import EmotionTtsResponse
from app.schemas.user_input import UserInputAnalysis
from app.services.llm import ChatGeneration


class ConversationPipelineTests(unittest.TestCase):
    def _dependencies(self, text="안녕"):
        analyzer = Mock()
        analyzer.analyze_text.return_value = UserInputAnalysis(
            user_text=text,
            user_emotion=Emotion.NORMAL,
            user_speaking_style=None,
            inferred_style="평범한 말투",
            user_intent="인사",
        )
        chat = Mock(
            return_value=ChatGeneration(
                answer="안녕하세요", response_style="밝은 말투"
            )
        )
        tts = Mock()
        tts.generate.return_value = EmotionTtsResponse(
            text="안녕하세요",
            speaking_style="밝은 말투",
            audio_path=str(Path("app/outputs/result.wav").resolve()),
            metadata_path=str(Path("app/outputs/result.json").resolve()),
            tts_provider="gemini",
            tts_model="gemini-3.1-flash-tts-preview",
            voice_name="Kore",
        )
        voice_analyzer = Mock()
        from app.schemas.voice_emotion import EmotionScore, VoiceEmotionAnalysis

        voice_analyzer.analyze.return_value = VoiceEmotionAnalysis(
            transcript=text,
            emotions=[
                EmotionScore(label="차분함", percentage=70),
                EmotionScore(label="친절함", percentage=20),
                EmotionScore(label="긴장감", percentage=10),
            ],
            impressions=["차분하게 들려요"],
            model="gemini-3.6-flash",
        )
        return analyzer, voice_analyzer, chat, tts

    def test_voice_runs_analysis_chat_and_tts_once(self):
        from app.schemas.conversation import VoiceConversationRequest
        from app.services.conversation_pipeline import ConversationPipelineService

        analyzer, voice_analyzer, chat, tts = self._dependencies()
        service = ConversationPipelineService(analyzer, voice_analyzer, chat, tts)

        result = service.process_voice(
            VoiceConversationRequest(
                transcript="안녕",
                persona="doyun",
                audio_base64="UklGRi1hdWRpbw==",
                audio_mime_type="audio/wav",
            )
        )

        self.assertEqual(result.input_type, "voice")
        self.assertEqual(result.answer, "안녕하세요")
        analyzer.analyze_text.assert_called_once_with("안녕")
        voice_analyzer.analyze.assert_called_once_with(
            audio_bytes=b"RIFF-audio",
            mime_type="audio/wav",
            transcript="안녕",
        )
        self.assertEqual(result.voice_emotion.emotions[0].label, "차분함")
        chat.assert_called_once()
        tts.generate.assert_called_once()

    def test_text_runs_the_same_pipeline_including_tts(self):
        from app.schemas.conversation import TextConversationRequest
        from app.services.conversation_pipeline import ConversationPipelineService

        analyzer, voice_analyzer, chat, tts = self._dependencies()
        service = ConversationPipelineService(analyzer, voice_analyzer, chat, tts)

        result = service.process_text(
            TextConversationRequest(text="안녕", persona="doyun")
        )

        self.assertEqual(result.input_type, "text")
        self.assertEqual(result.audio.voice_name, "Kore")
        analyzer.analyze_text.assert_called_once_with("안녕")
        voice_analyzer.analyze.assert_not_called()
        chat.assert_called_once()
        tts.generate.assert_called_once()

    def test_missing_response_style_stops_before_tts(self):
        from app.schemas.conversation import TextConversationRequest
        from app.services.conversation_pipeline import ConversationPipelineService

        analyzer, voice_analyzer, chat, tts = self._dependencies()
        chat.return_value = SimpleNamespace(answer="안녕하세요", response_style="")
        service = ConversationPipelineService(analyzer, voice_analyzer, chat, tts)

        with self.assertRaisesRegex(RuntimeError, "답변 말투"):
            service.process_text(
                TextConversationRequest(text="안녕", persona="doyun")
            )

        tts.generate.assert_not_called()

    def test_openapi_exposes_room_conversation_entrypoints(self):
        import app.main

        paths = app.main.app.openapi()["paths"]
        self.assertIn("/rooms/{room_id}/turns/voice", paths)
        self.assertIn("/rooms/{room_id}/turns/text", paths)
        self.assertIn("/rooms/{room_id}/audio/{filename}", paths)
        self.assertNotIn("/api/v1/input/voice", paths)
        self.assertNotIn("/api/v1/input/text", paths)
        self.assertNotIn("/api/v1/speech-pipeline/generate", paths)
        self.assertNotIn("/api/v1/user-input/text", paths)
        self.assertFalse(any(path.startswith("/api/v1/emotion-tts") for path in paths))
        self.assertNotIn("/tts", paths)


if __name__ == "__main__":
    unittest.main()
