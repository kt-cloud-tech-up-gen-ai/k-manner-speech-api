import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.core.config import TtsSettings
from app.routers import room_conversation
from app.schemas.emotion_tts import EmotionTtsRequest
from app.services.gemini_answer_audio_generator import GeminiAnswerAudioGenerator


class GeminiTtsTests(unittest.TestCase):
    @patch("app.services.gemini_answer_audio_generator.genai.Client")
    def test_synthesize_requests_audio_with_selected_voice(self, client_class):
        pcm = b"\x00\x00" * 100
        client = client_class.return_value
        client.models.generate_content.return_value = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=pcm))]
                    )
                )
            ]
        )
        settings = TtsSettings(
            google_api_key="test-key",
            tts_model="gemini-3.1-flash-tts-preview",
            voice_name="Kore",
            output_dir=Path("app/outputs"),
        )
        service = GeminiAnswerAudioGenerator(settings)

        result = service._synthesize("테스트 문장", "밝게 말한다.", "Kore")

        self.assertEqual(result, pcm)
        call = client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-3.1-flash-tts-preview")
        self.assertIn("테스트 문장", call.kwargs["contents"])
        self.assertIn("밝게 말한다", call.kwargs["contents"])
        self.assertEqual(
            call.kwargs["config"].speech_config.voice_config.prebuilt_voice_config.voice_name,
            "Kore",
        )

    def test_pipeline_saves_wav_and_gemini_metadata(self):
        with tempfile.TemporaryDirectory() as tempdir:
            settings = TtsSettings(
                google_api_key="test-key",
                tts_model="gemini-3.1-flash-tts-preview",
                voice_name="Kore",
                output_dir=Path(tempdir),
            )
            service = GeminiAnswerAudioGenerator(settings)
            service._synthesize = Mock(return_value=b"\x00\x00" * 100)
            request = EmotionTtsRequest(
                text="안녕하세요",
                speaking_style="밝고 친근한 목소리로 말한다.",
            )

            result = service.generate(request)

            self.assertEqual(result.tts_provider, "gemini")
            self.assertEqual(result.voice_name, "Kore")
            self.assertTrue(result.audio_path.endswith(".wav"))
            self.assertTrue(Path(result.metadata_path).is_file())
            with wave.open(result.audio_path, "rb") as wav_file:
                self.assertEqual(wav_file.getframerate(), 24_000)
                self.assertEqual(wav_file.getnchannels(), 1)
                self.assertEqual(wav_file.getsampwidth(), 2)

    def test_generated_wav_is_served_from_output_directory(self):
        with tempfile.TemporaryDirectory() as tempdir:
            audio_path = Path(tempdir) / "result.wav"
            audio_path.write_bytes(b"RIFF-test")
            settings = TtsSettings(
                google_api_key="test-key",
                tts_model="gemini-3.1-flash-tts-preview",
                voice_name="Kore",
                output_dir=Path(tempdir),
            )
            with (
                patch.object(
                    room_conversation, "get_tts_settings", return_value=settings
                ),
                patch.object(room_conversation, "_get_room_or_404"),
            ):
                response = room_conversation.get_generated_audio(
                    "room-1", "result.wav", Mock(), Mock()
                )

            self.assertEqual(Path(response.path).resolve(), audio_path.resolve())
            self.assertEqual(response.media_type, "audio/wav")

    def test_generated_audio_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tempdir:
            settings = TtsSettings(
                google_api_key="test-key",
                tts_model="gemini-3.1-flash-tts-preview",
                voice_name="Kore",
                output_dir=Path(tempdir),
            )
            with (
                patch.object(
                    room_conversation, "get_tts_settings", return_value=settings
                ),
                patch.object(room_conversation, "_get_room_or_404"),
            ):
                with self.assertRaises(HTTPException) as raised:
                    room_conversation.get_generated_audio(
                        "room-1", "../secret.wav", Mock(), Mock()
                    )

            self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
