"""Alembic 마이그레이션 검증 (plan-acc T1/T3).

SQLite 임시 파일 DB에 실제로 upgrade/downgrade를 돌려 스키마와 데이터 보존을 확인한다.
"""

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "5462e05b82eb"
SCHEMA_CHANGE = "7ea6b68d4729"
CATALOG = "9c1f4b0a7d52"


class MigrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "test.db"
        self.url = f"sqlite:///{db_path}"
        self.engine = create_engine(self.url)

        self.config = Config(str(PROJECT_ROOT / "alembic.ini"))
        self.config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        self.config.set_main_option("sqlalchemy.url", self.url)

    def tearDown(self):
        self.engine.dispose()
        self._tmpdir.cleanup()

    def upgrade(self, revision="head"):
        command.upgrade(self.config, revision)

    def downgrade(self, revision):
        command.downgrade(self.config, revision)

    def columns(self, table="chat_rooms"):
        return {c["name"]: c for c in inspect(self.engine).get_columns(table)}


class BaselineTests(MigrationTestCase):
    def test_upgrade_head_creates_all_tables(self):
        self.upgrade()
        tables = set(inspect(self.engine).get_table_names())
        self.assertEqual(
            {"alembic_version", "chat_rooms", "chat_messages"} - tables, set()
        )

    def test_downgrade_base_removes_domain_tables(self):
        self.upgrade()
        self.downgrade("base")
        tables = set(inspect(self.engine).get_table_names())
        self.assertNotIn("chat_rooms", tables)
        self.assertNotIn("chat_messages", tables)

    def test_head_schema_matches_models(self):
        """env.py가 모델을 import하지 않으면 이 diff가 비지 않는다."""
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext

        from app.core.db import Base
        from app.models import catalog, chat, user  # noqa: F401
        from migrations.autogenerate_filters import include_object

        self.upgrade()
        with self.engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"include_object": include_object}
            )
            diff = compare_metadata(context, Base.metadata)
        self.assertEqual(diff, [])


class SchemaChangeTests(MigrationTestCase):
    def _seed_baseline_rows(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_rooms (id, user_id, persona_id, scenario_id, title, created_at)"
                    " VALUES ('r1', 'u1', 'doyun', 'interview', '면접 연습', '2026-08-01 00:00:00')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO chat_rooms (id, user_id, persona_id, scenario_id, title, created_at)"
                    " VALUES ('r2', 'u1', 'doyun', NULL, NULL, '2026-08-02 00:00:00')"
                )
            )

    def test_title_is_renamed_and_backfilled(self):
        self.upgrade(BASELINE)
        self._seed_baseline_rows()
        self.upgrade(SCHEMA_CHANGE)

        with self.engine.connect() as connection:
            rows = dict(
                connection.execute(text("SELECT id, name FROM chat_rooms")).all()
            )
            timestamps = connection.execute(
                text("SELECT id, created_at, updated_at, last_message_at FROM chat_rooms")
            ).all()

        self.assertEqual(rows["r1"], "면접 연습")  # 기존 값 보존
        self.assertEqual(rows["r2"], "대화")  # NULL 백필
        for _id, created_at, updated_at, last_message_at in timestamps:
            self.assertEqual(updated_at, created_at)
            self.assertEqual(last_message_at, created_at)

    def test_new_columns_are_not_null_after_upgrade(self):
        self.upgrade(SCHEMA_CHANGE)
        columns = self.columns()
        self.assertFalse(columns["name"]["nullable"])
        self.assertFalse(columns["updated_at"]["nullable"])
        self.assertFalse(columns["last_message_at"]["nullable"])
        self.assertTrue(columns["last_message_preview"]["nullable"])
        self.assertTrue(columns["last_read_at"]["nullable"])
        self.assertNotIn("title", columns)

    def test_downgrade_restores_baseline_shape(self):
        self.upgrade(SCHEMA_CHANGE)
        self.downgrade(BASELINE)

        columns = self.columns()
        self.assertIn("title", columns)
        self.assertTrue(columns["title"]["nullable"])
        for removed in (
            "name",
            "updated_at",
            "last_message_at",
            "last_message_preview",
            "last_read_at",
        ):
            self.assertNotIn(removed, columns)

    def test_backfill_is_required_for_not_null(self):
        """백필이 없으면 NOT NULL 승격이 실패한다는 전제를 확인한다."""
        self.upgrade(BASELINE)
        self._seed_baseline_rows()
        with self.engine.begin() as connection:
            null_titles = connection.execute(
                text("SELECT COUNT(*) FROM chat_rooms WHERE title IS NULL")
            ).scalar()
        self.assertGreater(null_titles, 0)

        self.upgrade(SCHEMA_CHANGE)
        with self.engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM chat_rooms WHERE name IS NULL")
            ).scalar()
        self.assertEqual(remaining, 0)


class CatalogRevisionTests(MigrationTestCase):
    """personas/scenarios 신설 + 누락 테이블 보정 + chat_rooms FK (plan-acc KAN-16 T4)."""

    NEW_TABLES = (
        "personas",
        "scenarios",
        "user_profiles",
        "user_learning_goals",
        "chat_feedbacks",
    )

    def _seed_room(self, persona_id="doyun", scenario_id="interview", room_id="r1"):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_rooms"
                    " (id, user_id, persona_id, scenario_id, name,"
                    "  created_at, updated_at, last_message_at)"
                    " VALUES (:id, 'u1', :persona_id, :scenario_id, '방',"
                    "  :now, :now, :now)"
                ),
                {
                    "id": room_id,
                    "persona_id": persona_id,
                    "scenario_id": scenario_id,
                    "now": "2026-08-01 00:00:00",
                },
            )

    def test_upgrade_creates_new_tables(self):
        self.upgrade(CATALOG)
        tables = set(inspect(self.engine).get_table_names())
        for table in self.NEW_TABLES:
            with self.subTest(table=table):
                self.assertIn(table, tables)

    def _seed_constants(self):
        """리비전 모듈의 시드 상수를 읽는다. 시드의 출처는 이 상수뿐이다."""
        import importlib.util

        path = next(
            (PROJECT_ROOT / "migrations" / "versions").glob(f"{CATALOG}_*.py")
        )
        spec = importlib.util.spec_from_file_location("catalog_revision", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_seed_matches_revision_constants(self):
        revision = self._seed_constants()
        self.upgrade(CATALOG)

        with self.engine.connect() as connection:
            persona_ids = set(connection.execute(text("SELECT id FROM personas")).scalars())
            scenario_ids = set(
                connection.execute(text("SELECT id FROM scenarios")).scalars()
            )

        self.assertEqual(persona_ids, {row["id"] for row in revision.PERSONA_SEED})
        self.assertEqual(scenario_ids, {row["id"] for row in revision.SCENARIO_SEED})

    def test_seeded_rows_fill_every_required_column(self):
        """NOT NULL 컬럼이 시드에서 하나라도 비면 여기서 걸린다."""
        self.upgrade(CATALOG)
        required = {
            "personas": (
                "first_name",
                "age",
                "gender",
                "description",
                "relationship_description",
                "version",
            ),
            "scenarios": (
                "description",
                "communication_goal",
                "end_condition",
                "max_turns",
                "version",
            ),
        }
        with self.engine.connect() as connection:
            for table, columns in required.items():
                for column in columns:
                    with self.subTest(table=table, column=column):
                        nulls = connection.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
                        ).scalar()
                        self.assertEqual(nulls, 0)

    def test_no_migration_reads_prompt_yaml(self):
        """시드 값의 출처는 리비전 상수다. YAML을 다시 읽기 시작하면 이 테스트가 막는다."""
        for path in (PROJECT_ROOT / "migrations").rglob("*.py"):
            with self.subTest(path=path.name):
                self.assertNotIn("yaml", path.read_text(encoding="utf-8"))

    def test_chat_rooms_gets_catalog_foreign_keys(self):
        self.upgrade(CATALOG)
        fks = {
            fk["constrained_columns"][0]: fk["referred_table"]
            for fk in inspect(self.engine).get_foreign_keys("chat_rooms")
        }
        self.assertEqual(fks.get("persona_id"), "personas")
        self.assertEqual(fks.get("scenario_id"), "scenarios")
        self.assertNotIn("user_id", fks)

    def test_existing_rooms_survive_the_upgrade(self):
        self.upgrade(SCHEMA_CHANGE)
        self._seed_room()
        self.upgrade(CATALOG)

        with self.engine.connect() as connection:
            persona_id = connection.execute(
                text("SELECT persona_id FROM chat_rooms WHERE id='r1'")
            ).scalar()
        self.assertEqual(persona_id, "doyun")

    def test_orphan_reference_aborts_the_upgrade(self):
        """카탈로그에 없는 persona를 참조하는 방이 있으면 조용히 넘어가지 않는다."""
        self.upgrade(SCHEMA_CHANGE)
        self._seed_room(persona_id="ghost", scenario_id=None)

        with self.assertRaises(RuntimeError) as caught:
            self.upgrade(CATALOG)
        self.assertIn("ghost", str(caught.exception))

    def test_downgrade_removes_new_tables_and_foreign_keys(self):
        self.upgrade(CATALOG)
        self.downgrade(SCHEMA_CHANGE)

        tables = set(inspect(self.engine).get_table_names())
        for table in self.NEW_TABLES:
            with self.subTest(table=table):
                self.assertNotIn(table, tables)
        self.assertEqual(inspect(self.engine).get_foreign_keys("chat_rooms"), [])

    def test_upgrade_downgrade_upgrade_is_repeatable(self):
        self.upgrade(CATALOG)
        self.downgrade(SCHEMA_CHANGE)
        self.upgrade(CATALOG)
        self.assertIn("personas", set(inspect(self.engine).get_table_names()))


if __name__ == "__main__":
    unittest.main()
