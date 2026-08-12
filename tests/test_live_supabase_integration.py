"""Opt-in FastAPI lifecycle tests using real Supabase Auth and PostgreSQL."""

from __future__ import annotations

import os
import unittest
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402


@unittest.skipUnless(
    os.getenv("RUN_LIVE_SUPABASE_TESTS") == "1",
    "set RUN_LIVE_SUPABASE_TESTS=1 to use the live project",
)
class LiveApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        marker = uuid.uuid4().hex
        self.email = f"codex-live-api-{marker}@example.com"
        self.password = f"Kms-{marker}-Aa1!"
        self.user_id: str | None = None
        self.room_ids: list[str] = []

    def tearDown(self) -> None:
        self.client.close()
        with get_engine().begin() as connection:
            for room_id in self.room_ids:
                connection.execute(
                    text("DELETE FROM chat_rooms WHERE id = :room_id"),
                    {"room_id": room_id},
                )
            if self.user_id is not None:
                connection.execute(
                    text("DELETE FROM user_profiles WHERE user_id = :user_id"),
                    {"user_id": self.user_id},
                )
        if self.user_id is not None:
            secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            response = httpx.delete(
                f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1/admin/users/{self.user_id}",
                headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
                timeout=30,
            )
            self.assertIn(response.status_code, (200, 204, 404))

    def _signup(self) -> None:
        response = self.client.post(
            "/auth/signup", json={"email": self.email, "password": self.password}
        )
        self.assertEqual(response.status_code, 201, "AC-LIVE-COOKIE-LIFECYCLE")
        self.user_id = response.json()["user"]["id"]
        self.assertTrue(self.client.cookies.get("access_token"))
        self.assertTrue(self.client.cookies.get("refresh_token"))
        self.assertTrue(self.client.cookies.get("csrf_token"))

    def _csrf(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.client.cookies["csrf_token"]}

    def _catalog_persona(self) -> str:
        response = self.client.get("/personas")
        self.assertEqual(response.status_code, 200)
        return response.json()["personas"][0]["id"]

    def test_member_lifecycle(self) -> None:
        self._signup()
        profile = self.client.put(
            "/auth/me/profile",
            headers=self._csrf(),
            json={
                "name": "Codex Live",
                "age": 25,
                "learning_goal_other": None,
                "native_language": "ko",
                "gender": None,
                "learning_goals": ["daily_conversation"],
                "study_frequency": "weekly",
                "push_enabled": False,
            },
        )
        self.assertEqual(profile.status_code, 200, "AC-LIVE-COOKIE-LIFECYCLE")

        room = self.client.post(
            "/rooms",
            headers=self._csrf(),
            json={
                "persona_id": self._catalog_persona(),
                "scenario_id": None,
                "name": "Codex live member room",
            },
        )
        self.assertEqual(room.status_code, 201, "AC-LIVE-COOKIE-LIFECYCLE")
        room_id = room.json()["id"]
        self.room_ids.append(room_id)
        message = self.client.post(
            f"/rooms/{room_id}/messages",
            headers=self._csrf(),
            json={"question": "안녕하세요. 오늘 기분은 어떠세요?"},
        )
        self.assertEqual(message.status_code, 200, "AC-LIVE-COOKIE-LIFECYCLE")
        feedback = self.client.post(
            f"/rooms/{room_id}/feedback", headers=self._csrf()
        )
        self.assertEqual(feedback.status_code, 200, "AC-LIVE-COOKIE-LIFECYCLE")
        self.assertIn("score", feedback.json())

        logout = self.client.post("/auth/logout", headers=self._csrf())
        self.assertEqual(logout.status_code, 204)
        login = self.client.post(
            "/auth/login",
            data={"username": self.email, "password": self.password},
        )
        self.assertEqual(login.status_code, 200, "AC-LIVE-COOKIE-LIFECYCLE")
        withdraw = self.client.delete("/auth/me", headers=self._csrf())
        self.assertEqual(withdraw.status_code, 204, "AC-LIVE-COOKIE-LIFECYCLE")
        self.user_id = None

    def test_guest_limit_and_login_cleanup(self) -> None:
        room = self.client.post(
            "/rooms",
            json={
                "persona_id": self._catalog_persona(),
                "scenario_id": None,
                "name": "Codex live guest room",
            },
        )
        self.assertEqual(room.status_code, 201, "AC-LIVE-GUEST-THREE-TURNS")
        room_id = room.json()["id"]
        self.room_ids.append(room_id)
        for turn in range(3):
            response = self.client.post(
                f"/rooms/{room_id}/messages",
                headers=self._csrf(),
                json={"question": f"게스트 실제 대화 {turn + 1}번째입니다."},
            )
            self.assertEqual(response.status_code, 200, "AC-LIVE-GUEST-THREE-TURNS")

        rooms = self.client.get("/rooms").json()["rooms"]
        stored = next(item for item in rooms if item["id"] == room_id)
        self.assertEqual(stored["turn_count"], 3, "AC-LIVE-GUEST-THREE-TURNS")
        self.assertEqual(stored["status"], "completed", "AC-LIVE-GUEST-THREE-TURNS")
        fourth = self.client.post(
            f"/rooms/{room_id}/messages",
            headers=self._csrf(),
            json={"question": "네 번째 메시지"},
        )
        self.assertEqual(fourth.status_code, 409, "AC-LIVE-GUEST-THREE-TURNS")
        feedback = self.client.post(f"/rooms/{room_id}/feedback", headers=self._csrf())
        self.assertEqual(feedback.status_code, 403, "AC-LIVE-GUEST-THREE-TURNS")

        self._signup()
        with get_engine().connect() as connection:
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM chat_rooms WHERE id = :room_id"),
                {"room_id": room_id},
            ).scalar_one()
        self.assertEqual(remaining, 0, "AC-LIVE-GUEST-THREE-TURNS")
        withdraw = self.client.delete("/auth/me", headers=self._csrf())
        self.assertEqual(withdraw.status_code, 204)
        self.user_id = None


if __name__ == "__main__":
    unittest.main()
