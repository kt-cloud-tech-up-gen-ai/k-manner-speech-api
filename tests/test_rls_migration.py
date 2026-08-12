"""Contract tests for the Supabase Data API RLS migration."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "c7e1a4b92d60_harden_supabase_rls_policies.py"
ALEMBIC_ENV = ROOT / "migrations" / "env.py"


class RlsMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(MIGRATION.exists(), "AC-RLS-MIGRATION-EXISTS")
        self.source = MIGRATION.read_text(encoding="utf-8")
        spec = importlib.util.spec_from_file_location("rls_migration", MIGRATION)
        assert spec is not None and spec.loader is not None
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)

    def _upgrade_sql(self) -> str:
        statements: list[str] = []
        with (
            patch.object(self.migration, "_is_postgresql", return_value=True),
            patch.object(self.migration, "_execute", side_effect=statements.append),
        ):
            self.migration.upgrade()
        return "\n".join(statements)

    def test_policy_sql_matches_ownership_matrix(self) -> None:
        sql = self._upgrade_sql()
        for table in (
            "user_profiles",
            "user_learning_goals",
            "chat_rooms",
            "chat_messages",
            "chat_feedbacks",
        ):
            with self.subTest(table=table):
                self.assertIn(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY", sql)

        self.assertIn("auth.uid()::text = user_id", sql)
        self.assertIn("chat_rooms.user_id = auth.uid()::text", sql)
        self.assertIn("AC-RLS-OWNERSHIP-MATRIX", self.source)
        self.assertNotIn("USING (true)", sql)
        self.assertNotIn("user_tutorial_progress", self.source)

    def test_catalog_is_authenticated_read_only_and_anon_is_denied(self) -> None:
        sql = self._upgrade_sql()
        self.assertIn(
            "GRANT SELECT ON TABLE public.personas, public.scenarios, public.persona_scenarios TO authenticated",
            sql,
            "AC-RLS-CATALOG-READONLY",
        )
        self.assertNotIn("GRANT ALL ON personas", sql)
        self.assertIn("REVOKE ALL PRIVILEGES ON TABLE", sql)
        self.assertIn("FROM anon, authenticated", sql)

    def test_revision_chain_and_downgrade_are_precise(self) -> None:
        self.assertIn('down_revision = "b6d9f4e81a32"', self.source, "AC-LIVE-MIGRATION-CHAIN")
        self.assertIn("DROP POLICY IF EXISTS", self.source)
        self.assertNotIn("DROP TABLE", self.source.upper())
        self.assertNotIn("TRUNCATE", self.source.upper())

    def test_alembic_loads_repository_dotenv(self) -> None:
        source = ALEMBIC_ENV.read_text(encoding="utf-8")
        self.assertIn("load_dotenv", source, "AC-LIVE-ALEMBIC-DOTENV")
        self.assertIn('load_dotenv(PROJECT_ROOT / ".env")', source)


if __name__ == "__main__":
    unittest.main()
