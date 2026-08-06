import base64
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app as fastapi_app


def _make_client() -> tuple[TestClient, object]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import app.models.chat  # noqa: F401  테이블 등록  (주의: 이름 app 재바인딩)

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return TestClient(fastapi_app), engine


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client, self.engine = _make_client()

    def tearDown(self):
        fastapi_app.dependency_overrides.clear()
        self.client.close()
        Base.metadata.drop_all(bind=self.engine)

    def _create_room(self, **overrides):
        payload = {"user_id": "u1", "persona_id": "doyun", **overrides}
        return self.client.post("/rooms", json=payload)


class CatalogTests(ApiTestCase):
    def test_persona_list_contains_known_persona(self):
        response = self.client.get("/personas")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["personas"]]
        self.assertIn("doyun", ids)

    def test_scenario_list_contains_known_scenario(self):
        response = self.client.get("/scenarios")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["scenarios"]]
        self.assertIn("interview", ids)


class RoomTests(ApiTestCase):
    def test_create_room_returns_created_room(self):
        response = self._create_room(scenario_id="interview", title="면접 연습")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["persona_id"], "doyun")
        self.assertEqual(body["scenario_id"], "interview")
        self.assertTrue(body["id"])

    def test_create_room_with_unknown_persona_is_rejected(self):
        response = self._create_room(persona_id="nobody")
        self.assertEqual(response.status_code, 400)

    def test_create_room_with_unknown_scenario_is_rejected(self):
        response = self._create_room(scenario_id="does-not-exist")
        self.assertEqual(response.status_code, 400)

    def test_room_list_is_filtered_by_user(self):
        self._create_room(user_id="u1")
        self._create_room(user_id="u2")

        rooms = self.client.get("/rooms", params={"user_id": "u1"}).json()["rooms"]
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["user_id"], "u1")

    def test_room_list_requires_user_id(self):
        self.assertEqual(self.client.get("/rooms").status_code, 422)

    def test_messages_of_unknown_room_is_404(self):
        self.assertEqual(self.client.get("/rooms/none/messages").status_code, 404)


class SendMessageTests(ApiTestCase):
    @patch("app.routers.rooms.generate_answer", return_value="안녕하세요!")
    def test_message_and_answer_are_persisted(self, mock_generate):
        room_id = self._create_room().json()["id"]

        response = self.client.post(
            f"/rooms/{room_id}/messages", json={"question": "안녕"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "안녕하세요!")

        messages = self.client.get(f"/rooms/{room_id}/messages").json()["messages"]
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "안녕")
        self.assertEqual(mock_generate.call_args.kwargs["persona"], "doyun")

    @patch("app.routers.rooms.generate_answer", return_value="ok")
    def test_previous_history_is_passed_to_llm(self, mock_generate):
        room_id = self._create_room().json()["id"]
        self.client.post(f"/rooms/{room_id}/messages", json={"question": "첫 질문"})
        self.client.post(f"/rooms/{room_id}/messages", json={"question": "두번째"})

        history = mock_generate.call_args.kwargs["history"]
        self.assertEqual(history[0]["content"], "첫 질문")

    def test_blank_question_is_rejected(self):
        room_id = self._create_room().json()["id"]
        response = self.client.post(f"/rooms/{room_id}/messages", json={"question": " "})
        self.assertEqual(response.status_code, 400)

    def test_message_to_unknown_room_is_404(self):
        response = self.client.post("/rooms/none/messages", json={"question": "안녕"})
        self.assertEqual(response.status_code, 404)


class FeedbackTests(ApiTestCase):
    @patch("app.routers.rooms.generate_answer", return_value="네 안녕하세요")
    @patch(
        "app.services.feedback.invoke_llm",
        return_value='{"score": 80, "summary": "무난합니다.", "improvements": ["존댓말 유지"]}',
    )
    def test_feedback_returns_parsed_score(self, _mock_llm, _mock_answer):
        room_id = self._create_room().json()["id"]
        self.client.post(f"/rooms/{room_id}/messages", json={"question": "야 뭐해"})

        body = self.client.post(f"/rooms/{room_id}/feedback").json()
        self.assertEqual(body["score"], 80)
        self.assertEqual(body["improvements"], ["존댓말 유지"])

    def test_feedback_without_user_message_is_rejected(self):
        room_id = self._create_room().json()["id"]
        self.assertEqual(self.client.post(f"/rooms/{room_id}/feedback").status_code, 400)

    def test_feedback_of_unknown_room_is_404(self):
        self.assertEqual(self.client.post("/rooms/none/feedback").status_code, 404)

    def test_non_json_response_falls_back_to_summary(self):
        from app.services.feedback import parse_feedback

        result = parse_feedback("전반적으로 예의 바릅니다.")
        self.assertIsNone(result["score"])
        self.assertEqual(result["summary"], "전반적으로 예의 바릅니다.")


class TtsTests(ApiTestCase):
    @patch("app.services.tts.get_default_voice_id", return_value="voice-1")
    @patch("app.services.tts.get_api_key", return_value="test-key")
    @patch("app.services.tts.urlopen")
    def test_audio_is_returned_as_base64(self, mock_urlopen, _key, _voice):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b"audio-bytes"

        response = self.client.post("/tts", json={"text": "안녕하세요"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(base64.b64decode(body["audio"]), b"audio-bytes")
        self.assertEqual(body["mimeType"], "audio/mpeg")
        self.assertEqual(body["voice_id"], "voice-1")

    @patch("app.services.tts.get_default_voice_id", return_value=None)
    @patch("app.services.tts.get_api_key", return_value="test-key")
    def test_missing_voice_configuration_is_503(self, _key, _voice):
        response = self.client.post("/tts", json={"text": "안녕"})
        self.assertEqual(response.status_code, 503)

    @patch("app.services.tts.get_default_voice_id", return_value="voice-1")
    @patch("app.services.tts.get_api_key", return_value=None)
    def test_missing_api_key_is_503(self, _key, _voice):
        response = self.client.post("/tts", json={"text": "안녕"})
        self.assertEqual(response.status_code, 503)

    @patch("app.services.tts.get_default_voice_id", return_value="voice-1")
    @patch("app.services.tts.get_api_key", return_value="test-key")
    @patch("app.services.tts.urlopen")
    def test_upstream_400_is_client_error(self, mock_urlopen, _key, _voice):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.elevenlabs.io",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"invalid voice"}'),
        )
        response = self.client.post("/tts", json={"text": "안녕"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("invalid voice", response.text)

    def test_unknown_persona_is_rejected(self):
        response = self.client.post(
            "/tts", json={"text": "안녕", "persona_id": "nobody"}
        )
        self.assertEqual(response.status_code, 400)


class WebSpeechTests(ApiTestCase):
    def test_web_speech_test_page_is_served(self):
        response = self.client.get("/web-speech-test")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("SpeechRecognition", response.text)
        self.assertIn("ko-KR", response.text)


if __name__ == "__main__":
    unittest.main()
