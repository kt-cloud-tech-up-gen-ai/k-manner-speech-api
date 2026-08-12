import os
from unittest.mock import patch

from app.models.chat import ChatRoom
from tests.test_new_apis import SIGNUP_SESSION, ApiTestCase


class GuestRoomTests(ApiTestCase):
    def setUp(self):
        self.secret = patch.dict(os.environ, {"GUEST_SESSION_SECRET": "test-secret-32-bytes-minimum-value"})
        self.secret.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.secret.stop()

    def test_guest_cookie_owns_only_its_rooms(self):
        first = self.client.post(
            "/rooms", json={"persona_id": "doyun", "scenario_id": "interview", "name": "guest"}
        )
        self.assertEqual(first.status_code, 201, msg="AC-T4-GUEST-ISOLATION")
        guest_cookie = self.client.cookies.get("guest_session")
        self.assertTrue(guest_cookie, msg="AC-T4-GUEST-ISOLATION")
        self.assertIn("HttpOnly", first.headers.get("set-cookie", ""))

        room_id = first.json()["id"]
        self.client.cookies.set("guest_session", "tampered")
        hidden = self.client.get(f"/rooms/{room_id}/messages")
        self.assertEqual(hidden.status_code, 404, msg="AC-T4-GUEST-ISOLATION")


class GuestTurnTests(ApiTestCase):
    def setUp(self):
        self.secret = patch.dict(os.environ, {"GUEST_SESSION_SECRET": "test-secret-32-bytes-minimum-value"})
        self.secret.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.secret.stop()

    def test_third_guest_turn_completes_and_blocks_more_work(self):
        room = self.client.post(
            "/rooms", json={"persona_id": "doyun", "scenario_id": "interview", "name": "guest"}
        )
        self.assertEqual(room.status_code, 201)
        room_id = room.json()["id"]
        csrf = self.client.cookies.get("csrf_token")
        headers = {"X-CSRF-Token": csrf}
        with patch("app.routers.rooms.generate_answer", side_effect=["a1", "a2", "final"]):
            for number in range(1, 4):
                response = self.client.post(
                    f"/rooms/{room_id}/messages",
                    json={"question": f"q{number}"},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 200)

        with self.session() as session:
            stored = session.get(ChatRoom, room_id)
            self.assertEqual(stored.turn_count, 3, msg="AC-T5-GUEST-THREE-TURNS")
            self.assertEqual(stored.status.value, "completed", msg="AC-T5-GUEST-THREE-TURNS")
        fourth = self.client.post(
            f"/rooms/{room_id}/messages", json={"question": "q4"}, headers=headers
        )
        feedback = self.client.post(f"/rooms/{room_id}/feedback", headers=headers)
        self.assertEqual(fourth.status_code, 409, msg="AC-T5-GUEST-THREE-TURNS")
        self.assertEqual(feedback.status_code, 403, msg="AC-T5-GUEST-THREE-TURNS")


class GuestLoginPurgeTests(ApiTestCase):
    def setUp(self):
        self.secret = patch.dict(os.environ, {"GUEST_SESSION_SECRET": "test-secret-32-bytes-minimum-value"})
        self.secret.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.secret.stop()

    def test_login_deletes_guest_history(self):
        created = self.client.post(
            "/rooms", json={"persona_id": "doyun", "scenario_id": "interview", "name": "guest"}
        )
        room_id = created.json()["id"]
        with patch("app.routers.auth.sign_in_with_password", return_value=SIGNUP_SESSION):
            login = self.client.post(
                "/auth/login", data={"username": "a@b.c", "password": "secret-pw"}
            )
        self.assertEqual(login.status_code, 200, msg="AC-T6-GUEST-PURGED-ON-LOGIN")
        with self.session() as session:
            self.assertIsNone(
                session.get(ChatRoom, room_id), msg="AC-T6-GUEST-PURGED-ON-LOGIN"
            )
        self.assertIsNone(self.client.cookies.get("guest_session"))
