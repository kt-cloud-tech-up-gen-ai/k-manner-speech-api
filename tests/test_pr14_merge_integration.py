import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.main import app as fastapi_app
from app.models.chat import ChatRoom
from tests.test_new_apis import ApiTestCase


ROOT = Path(__file__).resolve().parents[1]


class Pr14MergeIntegrationTests(ApiTestCase):
    def setUp(self):
        self.guest_secret = patch.dict(
            os.environ,
            {"GUEST_SESSION_SECRET": "test-secret-32-bytes-minimum-value"},
        )
        self.guest_secret.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.guest_secret.stop()

    def test_app_keeps_infrastructure_and_analysis_routes(self):
        paths = fastapi_app.openapi()["paths"]
        self.assertIn("/api/v1/user-input/text", paths, "AC-PR14-APP-WIRING")
        web_speech = self.client.get("/web-speech-test")
        self.assertEqual(web_speech.status_code, 200, "AC-PR14-APP-WIRING")
        self.assertIn("SpeechRecognition", web_speech.text, "AC-PR14-APP-WIRING")

        middleware_names = {item.cls.__name__ for item in fastapi_app.user_middleware}
        for expected in ("CORSMiddleware", "CsrfMiddleware"):
            with self.subTest(expected=expected):
                self.assertIn(expected, middleware_names, "AC-PR14-APP-WIRING")

    @patch("app.routers.rooms.generate_structured_answer", create=True)
    def test_guest_analysis_third_turn_is_structured_and_completes(self, mock_generate):
        from app.services.llm import ChatGeneration

        mock_generate.return_value = ChatGeneration(
            answer="분석된 마지막 답변",
            response_style="따뜻하고 정중한 말투",
        )
        room = self.client.post(
            "/rooms",
            json={
                "persona_id": "doyun",
                "scenario_id": "interview",
                "name": "guest analysis",
            },
        )
        self.assertEqual(room.status_code, 201)
        room_id = room.json()["id"]
        headers = {"X-CSRF-Token": self.client.cookies.get("csrf_token")}

        with patch("app.routers.rooms.generate_answer", side_effect=["a1", "a2"]):
            for number in (1, 2):
                response = self.client.post(
                    f"/rooms/{room_id}/messages",
                    json={"question": f"q{number}"},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 200)

        third = self.client.post(
            f"/rooms/{room_id}/messages",
            json={
                "question": "마지막 질문",
                "analysis": {
                    "emotion": "보통",
                    "inferred_style": "정중한 말투",
                    "intent": "대화 계속",
                },
            },
            headers=headers,
        )

        self.assertEqual(third.status_code, 200, "AC-PR14-GUEST-STRUCTURED")
        self.assertEqual(third.json()["answer"], "분석된 마지막 답변")
        self.assertEqual(
            third.json()["response_style"],
            "따뜻하고 정중한 말투",
            "AC-PR14-GUEST-STRUCTURED",
        )
        mock_generate.assert_called_once()
        with self.session() as session:
            stored = session.get(ChatRoom, room_id)
            self.assertEqual(stored.turn_count, 3, "AC-PR14-GUEST-STRUCTURED")
            self.assertEqual(stored.status.value, "completed", "AC-PR14-GUEST-STRUCTURED")
            self.assertEqual(
                [message.content for message in stored.messages[-2:]],
                ["마지막 질문", "분석된 마지막 답변"],
                "AC-PR14-GUEST-STRUCTURED",
            )

    def test_provider_dependencies_and_docs_match_runtime(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        expected_once = (
            "google-genai>=1.0.0,<2.0.0",
            "langchain-google-genai==4.3.2",
            "openai==2.53.0",
        )
        for dependency in expected_once:
            with self.subTest(dependency=dependency):
                self.assertEqual(
                    requirements.count(dependency),
                    1,
                    "AC-PR14-PROVIDER-CONTRACT",
                )
        for variable in ("CHAT_MODEL", "EMOTION_MODEL", "OPENAI_API_KEY", "FEEDBACK_MODEL"):
            with self.subTest(variable=variable):
                self.assertIn(variable, readme, "AC-PR14-PROVIDER-CONTRACT")
                self.assertIn(f"{variable}=", env_example, "AC-PR14-PROVIDER-CONTRACT")
        self.assertNotIn("OPENAI_API_KEY=sk-", readme + env_example)

    def test_no_conflict_markers_remain(self):
        candidates = [ROOT / "README.md", ROOT / "requirements.txt"]
        candidates.extend((ROOT / "app").rglob("*.py"))
        for path in candidates:
            content = path.read_text(encoding="utf-8")
            for marker in ("<<<<<<<", "=======", ">>>>>>>"):
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker, content, "AC-PR14-NO-CONFLICT-MARKERS")


if __name__ == "__main__":
    unittest.main()
