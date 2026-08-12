import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "app" / "static" / "web_speech_test.html"


class WebSpeechEmotionPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_posts_final_transcript_for_emotion_analysis(self):
        self.assertIn("/api/v1/user-input/text", self.page)
        self.assertIn("method: 'POST'", self.page)
        self.assertIn("JSON.stringify({ text })", self.page)
        self.assertIn("await analyzeEmotion(transcript)", self.page)

    def test_analysis_is_forwarded_to_stateless_chat_generation(self):
        self.assertIn("/chat", self.page)
        self.assertIn("await generateChatResponse(text, body)", self.page)
        self.assertIn("emotion: analysis.user_emotion", self.page)
        self.assertIn("inferred_style: analysis.inferred_style", self.page)
        self.assertIn("intent: analysis.user_intent", self.page)
        self.assertIn('id="chatAnswer"', self.page)
        self.assertIn('id="responseStyle"', self.page)
        self.assertIn('id="chatStatus"', self.page)

    def test_keeps_listening_until_user_stops(self):
        self.assertIn("instance.continuous = true", self.page)
        self.assertIn("keepListening = true", self.page)
        self.assertIn("if (keepListening && !recognitionFailed)", self.page)
        self.assertIn("recognition = createRecognition()", self.page)
        self.assertIn("keepListening = false", self.page)

    def test_starting_microphone_clears_previous_session(self):
        start_handler = self.page.split("startButton.addEventListener('click'", 1)[1]
        start_handler = start_handler.split("stopButton.addEventListener", 1)[0]

        self.assertIn("analysisController?.abort()", start_handler)
        self.assertIn("transcriptElement.value = ''", start_handler)
        self.assertIn("finalTranscript = ''", start_handler)
        self.assertIn("clearAnalysis()", start_handler)
        self.assertNotIn("finalTranscript = transcriptElement.value.trim()", start_handler)

    def test_renders_accessible_emotion_result_and_error_state(self):
        self.assertIn('id="analysisStatus"', self.page)
        self.assertIn('aria-live="polite"', self.page)
        for field_id in ("emotion", "inferredStyle", "intent", "analysisTime"):
            with self.subTest(field_id=field_id):
                self.assertIn(f'id="{field_id}"', self.page)
        self.assertIn("response.ok", self.page)
        self.assertIn("analysisStatusElement.textContent", self.page)
        self.assertIn("감정 분석 서버에 연결하지 못했습니다", self.page)
        self.assertIn("HTTP ${response.status}", self.page)


if __name__ == "__main__":
    unittest.main()
