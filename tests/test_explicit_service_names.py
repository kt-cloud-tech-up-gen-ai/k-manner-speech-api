import unittest
from importlib.util import find_spec


class ExplicitServiceNameTests(unittest.TestCase):
    def test_user_text_analyzer_has_explicit_name(self):
        from app.services.gemini_user_text_analyzer import GeminiUserTextAnalyzer

        self.assertEqual(GeminiUserTextAnalyzer.__name__, "GeminiUserTextAnalyzer")

    def test_answer_audio_generator_has_explicit_name(self):
        from app.services.gemini_answer_audio_generator import (
            GeminiAnswerAudioGenerator,
        )

        self.assertEqual(
            GeminiAnswerAudioGenerator.__name__, "GeminiAnswerAudioGenerator"
        )

    def test_ambiguous_tts_module_is_removed(self):
        self.assertIsNone(find_spec("app.services.tts"))


if __name__ == "__main__":
    unittest.main()
