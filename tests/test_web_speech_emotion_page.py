import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "app" / "static" / "web_speech_test.html"


class WebSpeechEmotionPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_posts_transcript_and_persona_to_full_pipeline_once(self):
        self.assertIn("/api/v1/speech-pipeline/generate", self.page)
        self.assertIn("method: 'POST'", self.page)
        self.assertIn("JSON.stringify({ text, persona })", self.page)
        self.assertIn("await runSpeechPipeline(transcript)", self.page)
        self.assertNotIn("fetch('/api/v1/user-input/text'", self.page)
        self.assertNotIn("fetch('/chat'", self.page)

    def test_renders_pipeline_results_and_playable_audio(self):
        self.assertIn("body.analysis.user_emotion", self.page)
        self.assertIn("body.analysis.inferred_style", self.page)
        self.assertIn("body.analysis.user_intent", self.page)
        self.assertIn("body.answer", self.page)
        self.assertIn("body.response_style", self.page)
        self.assertIn("body.processing_time_ms", self.page)
        self.assertIn('id="chatAnswer"', self.page)
        self.assertIn('id="responseStyle"', self.page)
        self.assertIn('id="ttsAudio"', self.page)
        self.assertIn("/api/v1/emotion-tts/audio/", self.page)
        self.assertIn("audioElement.load()", self.page)

    def test_has_labeled_persona_and_accessible_pipeline_status(self):
        self.assertIn('for="persona"', self.page)
        self.assertIn('id="persona"', self.page)
        self.assertIn('id="pipelineStatus"', self.page)
        self.assertIn('aria-live="polite"', self.page)
        self.assertIn("pipelineStatusElement.textContent", self.page)
        self.assertIn("audioElement.removeAttribute('src')", self.page)

    def test_keeps_listening_until_user_stops(self):
        self.assertIn("instance.continuous = true", self.page)
        self.assertIn("keepListening = true", self.page)
        self.assertIn("if (keepListening && !recognitionFailed)", self.page)
        self.assertIn("recognition = createRecognition()", self.page)
        self.assertIn("keepListening = false", self.page)

    def test_starting_microphone_clears_previous_session(self):
        start_handler = self.page.split("startButton.addEventListener('click'", 1)[1]
        start_handler = start_handler.split("stopButton.addEventListener", 1)[0]

        self.assertIn("pipelineController?.abort()", start_handler)
        self.assertIn("transcriptElement.value = ''", start_handler)
        self.assertIn("finalTranscript = ''", start_handler)
        self.assertIn("clearPipelineResult()", start_handler)
        self.assertNotIn("finalTranscript = transcriptElement.value.trim()", start_handler)

    def test_renders_accessible_emotion_result_and_error_state(self):
        self.assertIn('id="pipelineStatus"', self.page)
        self.assertIn('aria-live="polite"', self.page)
        for field_id in ("emotion", "inferredStyle", "intent", "pipelineTime"):
            with self.subTest(field_id=field_id):
                self.assertIn(f'id="{field_id}"', self.page)
        self.assertIn("response.ok", self.page)
        self.assertIn("pipelineStatusElement.textContent", self.page)
        self.assertIn("통합 파이프라인 서버에 연결하지 못했습니다", self.page)
        self.assertIn("HTTP ${response.status}", self.page)


if __name__ == "__main__":
    unittest.main()
