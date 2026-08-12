import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import DEFAULT_CORS_ALLOW_ORIGINS, get_cors_allow_origins
from app.main import app as fastapi_app


class CorsOriginConfigTests(unittest.TestCase):
    def test_unset_env_falls_back_to_local_dev_origins(self):
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("CORS_ALLOW_ORIGINS", None)
            self.assertEqual(get_cors_allow_origins(), list(DEFAULT_CORS_ALLOW_ORIGINS))

    def test_empty_env_does_not_produce_an_unmatchable_origin(self):
        # "".split(",") == [""] — 빈 항목이 남으면 어떤 출처와도 매칭되지 않아 전면 차단된다.
        with patch.dict("os.environ", {"CORS_ALLOW_ORIGINS": "  ,  "}):
            self.assertEqual(get_cors_allow_origins(), list(DEFAULT_CORS_ALLOW_ORIGINS))

    def test_entries_are_trimmed_and_trailing_slash_removed(self):
        raw = " https://app.example.com/ ,http://localhost:5173"
        with patch.dict("os.environ", {"CORS_ALLOW_ORIGINS": raw}):
            self.assertEqual(
                get_cors_allow_origins(),
                ["https://app.example.com", "http://localhost:5173"],
            )


class CorsPreflightTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(fastapi_app)

    def test_delete_room_preflight_is_allowed_for_dev_origin(self):
        response = self.client.options(
            "/rooms/1",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "authorization",
            },
        )

        self.assertEqual(response.status_code, 200)
        # 자격 증명을 쓰므로 출처는 와일드카드가 아니라 요청 출처가 그대로 돌아와야 한다.
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://localhost:5173"
        )
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        self.assertIn("DELETE", response.headers["access-control-allow-methods"])
        self.assertIn("authorization", response.headers["access-control-allow-headers"].lower())

    def test_unlisted_origin_is_rejected(self):
        response = self.client.options(
            "/rooms/1",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "DELETE",
            },
        )

        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
