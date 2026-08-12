"""Safety checks for opt-in tests against the live Supabase project."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.live_supabase import validate_live_supabase_environment


class LiveSupabaseConfigTests(unittest.TestCase):
    def test_target_ref_and_secret_hygiene(self) -> None:
        environment = {
            "DATABASE_URL": (
                "postgresql+psycopg://postgres.dlgjsarbbblmsscxrqrt:password@"
                "aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
            ),
            "SUPABASE_URL": "https://dlgjsarbbblmsscxrqrt.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-test-value",
            "SUPABASE_SERVICE_ROLE_KEY": "secret-test-value",
            "GUEST_SESSION_SECRET": "guest-test-secret-at-least-32-bytes",
        }
        with patch.dict("os.environ", environment, clear=True):
            result = validate_live_supabase_environment()

        self.assertEqual(result.project_ref, "dlgjsarbbblmsscxrqrt", "AC-LIVE-CONFIG-TARGET")
        self.assertEqual(result.pooler_host, "aws-0-ap-southeast-2.pooler.supabase.com")
        self.assertNotIn("password", repr(result))
        self.assertNotIn("publishable-test-value", repr(result))
        self.assertNotIn("secret-test-value", repr(result))

    def test_previous_project_or_incomplete_secrets_are_rejected(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://postgres.nfdkddajydfwcwddeoyn:x@old.example/postgres",
                "SUPABASE_URL": "https://nfdkddajydfwcwddeoyn.supabase.co",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "AC-LIVE-CONFIG-TARGET"):
                validate_live_supabase_environment()


if __name__ == "__main__":
    unittest.main()
