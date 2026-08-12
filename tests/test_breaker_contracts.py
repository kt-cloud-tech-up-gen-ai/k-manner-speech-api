import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers import rooms

ROOT = Path(__file__).resolve().parents[1]


class BreakerContractTests(unittest.TestCase):
    def test_supabase_publishable_key_fallback_is_wired(self) -> None:
        source = (ROOT / "app/core/auth.py").read_text(encoding="utf-8")
        self.assertIn(
            'os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")',
            source,
            "AC-LIVE-CONFIG-TARGET",
        )

    def test_owned_rls_policy_is_not_unconditional(self) -> None:
        source = (ROOT / "migrations/versions/a1c4e8f52b70_rls_data_api_policies.py").read_text(encoding="utf-8")
        self.assertIn(
            '_replace_all_policy("user_profiles", "auth.uid()::text = user_id")',
            source,
            "AC-RLS-OWNERSHIP-MATRIX",
        )

    def test_catalog_grant_remains_select_only(self) -> None:
        source = (ROOT / "migrations/versions/a1c4e8f52b70_rls_data_api_policies.py").read_text(encoding="utf-8")
        self.assertIn(
            '"GRANT SELECT ON TABLE public.personas, public.scenarios, "',
            source,
            "AC-RLS-CATALOG-READONLY",
        )

    def test_message_rls_uses_room_owner(self) -> None:
        source = (ROOT / "migrations/versions/a1c4e8f52b70_rls_data_api_policies.py").read_text(encoding="utf-8")
        self.assertIn(
            '_replace_all_policy("chat_messages", message_owner)',
            source,
            "AC-RLS-TWO-USER-ISOLATION",
        )

    def test_profile_guest_revision_keeps_chain(self) -> None:
        source = (ROOT / "migrations/versions/f8b3c9d21a40_profile_and_guest_ownership.py").read_text(encoding="utf-8")
        self.assertIn('down_revision = "e7a2f4c81b09"', source, "AC-LIVE-MIGRATION-CHAIN")

    def test_access_cookie_name_is_used_for_session_install(self) -> None:
        source = (ROOT / "app/routers/auth.py").read_text(encoding="utf-8")
        self.assertIn("        ACCESS_COOKIE,", source, "AC-LIVE-COOKIE-LIFECYCLE")

    def test_guest_limit_is_three(self) -> None:
        self.assertEqual(rooms.GUEST_MAX_TURNS, 3, "AC-LIVE-GUEST-THREE-TURNS")

    def test_local_front_cors_allows_credentials(self) -> None:
        with TestClient(app) as client:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
        self.assertEqual(response.status_code, 200, "AC-E2E-LIVE-COOKIE-FLOW")
        self.assertEqual(
            response.headers.get("access-control-allow-credentials"),
            "true",
            "AC-E2E-LIVE-COOKIE-FLOW",
        )

    def test_error_log_shape_excludes_exception_secret(self) -> None:
        source = (ROOT / "app/core/errors.py").read_text(encoding="utf-8")
        self.assertIn(
            '{"request_id": request_id, "path": request.url.path, "status": 500}',
            source,
            "AC-LOG-NO-SECRETS",
        )


if __name__ == "__main__":
    unittest.main()
