import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Pr19MergeIntegrationTests(unittest.TestCase):
    def test_voice_emotion_and_scenario_contract_survive_merge(self):
        pipeline = (ROOT / "app/services/conversation_pipeline.py").read_text(encoding="utf-8")

        self.assertNotIn("<<<<<<<", pipeline, "AC-PR19-NO-CONFLICT-MARKERS")
        self.assertIn("scenario=scenario", pipeline, "AC-PR19-SCENARIO-PROPAGATION")
        self.assertIn("voice_emotion=voice_emotion", pipeline, "AC-PR19-VOICE-EMOTION")
        self.assertIn("def replace_answer", pipeline, "AC-PR19-EXIT-TTS-REPLACEMENT")


if __name__ == "__main__":
    unittest.main()
