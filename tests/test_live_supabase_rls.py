"""Opt-in RLS checks against the configured live Supabase project."""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv

from app.core.live_supabase import validate_live_supabase_environment


@unittest.skipUnless(
    os.getenv("RUN_LIVE_SUPABASE_TESTS") == "1",
    "set RUN_LIVE_SUPABASE_TESTS=1 to use the live project",
)
class LiveRlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_dotenv()
        validate_live_supabase_environment()
        cls.base_url = os.environ["SUPABASE_URL"].rstrip("/")
        cls.publishable = os.getenv("SUPABASE_ANON_KEY") or os.environ[
            "SUPABASE_PUBLISHABLE_KEY"
        ]
        cls.secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        cls.client = httpx.Client(timeout=30)
        cls.users: list[dict[str, str]] = []
        cls.guest_room_ids: list[str] = []
        try:
            for _ in range(2):
                marker = uuid.uuid4().hex
                response = cls.client.post(
                    f"{cls.base_url}/auth/v1/signup",
                    headers={"apikey": cls.publishable},
                    json={
                        "email": f"codex-live-{marker}@example.com",
                        "password": f"Kms-{marker}-Aa1!",
                    },
                )
                if response.status_code != 200:
                    raise AssertionError(
                        f"AC-LIVE-AUTH-CONFIRM: signup returned {response.status_code}"
                    )
                body = response.json()
                cls.users.append(
                    {"id": body["user"]["id"], "token": body["access_token"]}
                )
        except Exception:
            cls._delete_users()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        cls._delete_users()
        cls.client.close()

    @classmethod
    def _delete_users(cls) -> None:
        service_headers = {
            "apikey": cls.secret,
            "Authorization": f"Bearer {cls.secret}",
        }
        for room_id in cls.guest_room_ids:
            cls.client.delete(
                f"{cls.base_url}/rest/v1/chat_rooms?id=eq.{room_id}",
                headers=service_headers,
            )
        cls.guest_room_ids.clear()
        for user in cls.users:
            for table in ("chat_rooms", "user_profiles"):
                cleanup = cls.client.delete(
                    f"{cls.base_url}/rest/v1/{table}?user_id=eq.{user['id']}",
                    headers=service_headers,
                )
                if cleanup.status_code not in (200, 204):
                    raise AssertionError(
                        f"live {table} cleanup returned {cleanup.status_code}"
                    )
            response = cls.client.delete(
                f"{cls.base_url}/auth/v1/admin/users/{user['id']}",
                headers=service_headers,
            )
            if response.status_code not in (200, 204, 404):
                raise AssertionError(
                    f"live user cleanup returned {response.status_code}"
                )
        cls.users.clear()

    def _headers(self, user: dict[str, str]) -> dict[str, str]:
        return {
            "apikey": self.publishable,
            "Authorization": f"Bearer {user['token']}",
            "Content-Type": "application/json",
        }

    def test_catalog_read_only_and_anon_denied(self) -> None:
        authenticated = self.client.get(
            f"{self.base_url}/rest/v1/personas?select=id&limit=1",
            headers=self._headers(self.users[0]),
        )
        self.assertEqual(authenticated.status_code, 200, "AC-RLS-CATALOG-READONLY")
        persona_id = authenticated.json()[0]["id"]
        mutation = self.client.patch(
            f"{self.base_url}/rest/v1/personas?id=eq.{persona_id}",
            headers=self._headers(self.users[0]),
            json={"id": persona_id},
        )
        self.assertIn(mutation.status_code, (401, 403), "AC-RLS-CATALOG-READONLY")

        anonymous = self.client.get(
            f"{self.base_url}/rest/v1/personas?select=id&limit=1",
            headers={"apikey": self.publishable},
        )
        self.assertIn(anonymous.status_code, (401, 403), "AC-RLS-CATALOG-READONLY")

    def test_two_user_crud_isolation_and_guest_denial(self) -> None:
        owner, other = self.users
        created = self.client.post(
            f"{self.base_url}/rest/v1/user_profiles",
            headers={**self._headers(owner), "Prefer": "return=representation"},
            json={
                "user_id": owner["id"],
                "push_enabled": False,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        self.assertIn(
            created.status_code,
            (200, 201),
            f"AC-RLS-TWO-USER-ISOLATION: {created.text}",
        )

        hidden = self.client.get(
            f"{self.base_url}/rest/v1/user_profiles?user_id=eq.{owner['id']}",
            headers=self._headers(other),
        )
        self.assertEqual(hidden.status_code, 200, "AC-RLS-TWO-USER-ISOLATION")
        self.assertEqual(hidden.json(), [], "AC-RLS-TWO-USER-ISOLATION")

        visible = self.client.get(
            f"{self.base_url}/rest/v1/user_profiles?user_id=eq.{owner['id']}",
            headers=self._headers(owner),
        )
        self.assertEqual(visible.status_code, 200, "AC-RLS-TWO-USER-ISOLATION")
        self.assertEqual(len(visible.json()), 1, "AC-RLS-TWO-USER-ISOLATION")

        goal = self.client.post(
            f"{self.base_url}/rest/v1/user_learning_goals",
            headers=self._headers(owner),
            json={"user_id": owner["id"], "goal": "daily_conversation"},
        )
        self.assertIn(goal.status_code, (200, 201), "AC-RLS-TWO-USER-ISOLATION")

        persona = self.client.get(
            f"{self.base_url}/rest/v1/personas?select=id&limit=1",
            headers=self._headers(owner),
        ).json()[0]["id"]
        room_id = uuid.uuid4().hex
        timestamp = datetime.now(UTC).isoformat()
        room_payload = {
            "id": room_id,
            "user_id": owner["id"],
            "guest_id": None,
            "persona_id": persona,
            "scenario_id": None,
            "name": "live rls matrix",
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_message_at": timestamp,
            "status": "in_progress",
            "turn_count": 0,
        }
        room = self.client.post(
            f"{self.base_url}/rest/v1/chat_rooms",
            headers=self._headers(owner),
            json=room_payload,
        )
        self.assertIn(room.status_code, (200, 201), "AC-RLS-TWO-USER-ISOLATION")

        message_id = uuid.uuid4().hex
        message = self.client.post(
            f"{self.base_url}/rest/v1/chat_messages",
            headers=self._headers(owner),
            json={
                "id": message_id,
                "room_id": room_id,
                "role": "user",
                "content": "RLS test",
                "created_at": timestamp,
            },
        )
        self.assertIn(message.status_code, (200, 201), "AC-RLS-TWO-USER-ISOLATION")

        feedback = self.client.post(
            f"{self.base_url}/rest/v1/chat_feedbacks",
            headers=self._headers(owner),
            json={
                "id": uuid.uuid4().hex,
                "room_id": room_id,
                "last_message_id": message_id,
                "model": "live-rls-test",
                "prompt_version": "v1",
                "score": 100,
                "result_json": {},
                "created_at": timestamp,
            },
        )
        self.assertIn(feedback.status_code, (200, 201), "AC-RLS-TWO-USER-ISOLATION")

        for table in ("user_learning_goals", "chat_rooms", "chat_messages", "chat_feedbacks"):
            hidden = self.client.get(
                f"{self.base_url}/rest/v1/{table}?select=*",
                headers=self._headers(other),
            )
            self.assertEqual(hidden.status_code, 200, "AC-RLS-TWO-USER-ISOLATION")
            self.assertEqual(hidden.json(), [], "AC-RLS-TWO-USER-ISOLATION")

        guest_room_id = uuid.uuid4().hex
        self.guest_room_ids.append(guest_room_id)
        service_headers = {
            "apikey": self.secret,
            "Authorization": f"Bearer {self.secret}",
        }
        guest_payload = {
            **room_payload,
            "id": guest_room_id,
            "user_id": None,
            "guest_id": uuid.uuid4().hex,
            "name": "live guest rls matrix",
        }
        guest_room = self.client.post(
            f"{self.base_url}/rest/v1/chat_rooms",
            headers=service_headers,
            json=guest_payload,
        )
        self.assertIn(guest_room.status_code, (200, 201), "AC-RLS-TWO-USER-ISOLATION")
        guest_hidden = self.client.get(
            f"{self.base_url}/rest/v1/chat_rooms?id=eq.{guest_room_id}",
            headers=self._headers(owner),
        )
        self.assertEqual(guest_hidden.json(), [], "AC-RLS-TWO-USER-ISOLATION")


if __name__ == "__main__":
    unittest.main()
