"""Alembic 마이그레이션 검증 (plan-acc T1/T3).

SQLite 임시 파일 DB에 실제로 upgrade/downgrade를 돌려 스키마와 데이터 보존을 확인한다.
"""

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "5462e05b82eb"
SCHEMA_CHANGE = "7ea6b68d4729"
CATALOG = "9c1f4b0a7d52"
PERSONA_SCENARIOS = "b4d7e2a13c60"
PROGRESS = "c3f1a9d5e274"
CAMPUS_DIRECTIONS = "d5b8c07f9a13"
FREE_CHAT_UNIQUE = "e7a2f4c81b09"


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
                        # noqa 사유: table·column은 위 required 딕셔너리의 리터럴이며
                        # 식별자라 바인드 파라미터로 넘길 수 없다.
                        nulls = connection.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")  # noqa: S608
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


class PersonaScenarioRevisionTests(MigrationTestCase):
    """persona ↔ scenario N:N 매핑 테이블 (b4d7e2a13c60)."""

    def test_upgrade_creates_join_table_with_composite_key(self):
        self.upgrade(PERSONA_SCENARIOS)
        inspector = inspect(self.engine)
        self.assertIn("persona_scenarios", inspector.get_table_names())
        self.assertEqual(
            inspector.get_pk_constraint("persona_scenarios")["constrained_columns"],
            ["persona_id", "scenario_id"],
        )

    def test_foreign_keys_point_at_catalog(self):
        self.upgrade(PERSONA_SCENARIOS)
        targets = {
            fk["constrained_columns"][0]: fk["referred_table"]
            for fk in inspect(self.engine).get_foreign_keys("persona_scenarios")
        }
        self.assertEqual(targets["persona_id"], "personas")
        self.assertEqual(targets["scenario_id"], "scenarios")

    def test_seeded_pairs_reference_existing_catalog_rows(self):
        """조합 시드는 9c1f4b0a7d52가 넣은 카탈로그 안의 값이어야 한다.

        FK가 막아 줄 것이라고 기대하면 안 된다. SQLite는 마이그레이션 중 FK를 강제하지
        않으므로(PRAGMA 미설정) 카탈로그에 없는 값을 시드해도 upgrade가 그대로 성공하고
        고아 행이 남는다. 실제로 확인한 동작이다. 이 단언이 유일한 방어선이다.
        """
        self.upgrade(PERSONA_SCENARIOS)
        with self.engine.connect() as connection:
            pairs = set(
                connection.execute(
                    text("SELECT persona_id, scenario_id FROM persona_scenarios")
                ).all()
            )
            personas = set(connection.execute(text("SELECT id FROM personas")).scalars())
            scenarios = set(
                connection.execute(text("SELECT id FROM scenarios")).scalars()
            )

        self.assertTrue(pairs)
        for persona_id, scenario_id in pairs:
            with self.subTest(pair=(persona_id, scenario_id)):
                self.assertIn(persona_id, personas)
                self.assertIn(scenario_id, scenarios)

    def test_downgrade_removes_join_table_only(self):
        self.upgrade(PERSONA_SCENARIOS)
        self.downgrade(CATALOG)

        tables = set(inspect(self.engine).get_table_names())
        self.assertNotIn("persona_scenarios", tables)
        self.assertIn("personas", tables)
        self.assertIn("scenarios", tables)

    def test_upgrade_downgrade_upgrade_is_repeatable(self):
        self.upgrade(PERSONA_SCENARIOS)
        self.downgrade(CATALOG)
        self.upgrade(PERSONA_SCENARIOS)
        self.assertIn("persona_scenarios", set(inspect(self.engine).get_table_names()))


class ProgressColumnsRevisionTests(MigrationTestCase):
    """chat_rooms 진행 상태·턴 수 (c3f1a9d5e274)."""

    def _seed_room(self, room_id, scenario_id, assistant_messages):
        """이전 리비전 시점의 방과 대화 이력을 넣는다(진행 컬럼이 아직 없는 상태)."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_rooms"
                    " (id, user_id, persona_id, scenario_id, name,"
                    "  created_at, updated_at, last_message_at)"
                    " VALUES (:id, 'u1', 'doyun', :scenario_id, '방', :now, :now, :now)"
                ),
                {"id": room_id, "scenario_id": scenario_id, "now": "2026-08-01 00:00:00"},
            )
            for index in range(assistant_messages):
                # 사용자 발화와 persona 응답이 한 왕복. 턴 수는 assistant 쪽으로 센다.
                for role in ("user", "assistant"):
                    connection.execute(
                        text(
                            "INSERT INTO chat_messages (id, room_id, role, content, created_at)"
                            " VALUES (:id, :room_id, :role, '내용', :now)"
                        ),
                        {
                            "id": f"{room_id}-{role}-{index}",
                            "room_id": room_id,
                            "role": role,
                            "now": "2026-08-01 00:00:00",
                        },
                    )

    def test_upgrade_adds_not_null_progress_columns(self):
        self.upgrade(PROGRESS)
        columns = self.columns()
        for name in ("status", "turn_count"):
            with self.subTest(column=name):
                self.assertIn(name, columns)
                self.assertFalse(columns[name]["nullable"])

    def test_turn_count_is_backfilled_from_assistant_messages(self):
        """기존 방이 0턴으로 초기화되면 안 된다."""
        self.upgrade(PERSONA_SCENARIOS)
        self._seed_room("r-mid", scenario_id="interview", assistant_messages=3)
        self.upgrade(PROGRESS)

        with self.engine.connect() as connection:
            turn_count, status = connection.execute(
                text("SELECT turn_count, status FROM chat_rooms WHERE id='r-mid'")
            ).one()
        self.assertEqual(turn_count, 3)
        self.assertEqual(status, "in_progress")

    def test_room_at_max_turns_is_backfilled_as_completed(self):
        """max_turns에 도달한 기존 방까지 in_progress로 두면 애플리케이션 불변식이 깨진다."""
        self.upgrade(PERSONA_SCENARIOS)
        # interview의 max_turns는 20 (9c1f4b0a7d52 시드).
        self._seed_room("r-done", scenario_id="interview", assistant_messages=20)
        self.upgrade(PROGRESS)

        with self.engine.connect() as connection:
            status = connection.execute(
                text("SELECT status FROM chat_rooms WHERE id='r-done'")
            ).scalar()
        self.assertEqual(status, "completed")

    def test_room_without_scenario_stays_in_progress(self):
        """시나리오가 없으면 상한이 없으므로 자동 완료 대상이 아니다.

        마이그레이션의 `scenario_id IS NOT NULL` 조건을 지워도 이 테스트는 통과한다
        (하위 질의가 NULL이라 비교가 참이 되지 않는다). 이 테스트가 실제로 막는 것은
        상한을 0으로 취급하는 오구현(`COALESCE(max_turns, 0)`)이며, 그 경우 실패한다.
        """
        self.upgrade(PERSONA_SCENARIOS)
        self._seed_room("r-free", scenario_id=None, assistant_messages=50)
        self.upgrade(PROGRESS)

        with self.engine.connect() as connection:
            status = connection.execute(
                text("SELECT status FROM chat_rooms WHERE id='r-free'")
            ).scalar()
        self.assertEqual(status, "in_progress")

    def test_status_check_constraint_rejects_unknown_value(self):
        """autogenerate가 CHECK를 비교하지 않으므로, 실제 DB에 넣어 봐야만 확인된다."""
        self.upgrade(PROGRESS)

        with self.assertRaises(IntegrityError) as caught:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO chat_rooms"
                        " (id, user_id, persona_id, name, created_at, updated_at,"
                        "  last_message_at, status, turn_count)"
                        " VALUES ('r-bad', 'u1', 'doyun', '방', :now, :now, :now, 'done', 0)"
                    ),
                    {"now": "2026-08-08 00:00:00"},
                )
        self.assertIn("ck_chat_rooms_status", str(caught.exception))

    def test_downgrade_removes_progress_columns(self):
        self.upgrade(PROGRESS)
        self.downgrade(PERSONA_SCENARIOS)

        columns = self.columns()
        self.assertNotIn("status", columns)
        self.assertNotIn("turn_count", columns)
        self.assertIn("persona_scenarios", set(inspect(self.engine).get_table_names()))

    def test_upgrade_downgrade_upgrade_is_repeatable(self):
        self.upgrade(PROGRESS)
        self.downgrade(PERSONA_SCENARIOS)
        self.upgrade(PROGRESS)
        self.assertIn("status", self.columns())


class OfflineSqlTests(MigrationTestCase):
    """`alembic upgrade --sql`이 시드 값을 제대로 렌더하는가.

    DBA에게 넘길 SQL 스크립트를 뽑는 경로다. `op.get_bind().execute(text, params)`로
    시드를 넣으면 온라인 실행은 멀쩡한데 오프라인에서는 파라미터가 바인딩되지 않아
    `VALUES (NULL, NULL)`이 나온다. 조용히 잘못된 스크립트가 만들어지므로 여기서 막는다.

    범위의 시작은 카탈로그 리비전의 **직전**(SCHEMA_CHANGE)이다. `X:Y`는 X를 제외하고
    Y까지이므로, CATALOG에서 시작하면 정작 시드를 넣는 9c1f4b0a7d52 자신이 검사에서
    빠진다(실제로 그 리비전에 두 결함이 다 있었는데 통과하고 있었다).
    """

    def _offline_sql(self, revision_range):
        """PostgreSQL 방언으로 렌더한다. 접속은 하지 않는다.

        SQLite로는 이 검사를 할 수 없다. batch 연산이 테이블 반영(reflection)을 요구해서
        --sql 모드에서 실패한다. 오프라인 스크립트를 뽑는 대상은 운영 DB이므로 방언도
        그쪽에 맞춘다.
        """
        import io

        self.config.set_main_option(
            "sqlalchemy.url", "postgresql+psycopg://user:pass@localhost/db"
        )
        buffer = io.StringIO()
        self.config.output_buffer = buffer
        command.upgrade(self.config, revision_range, sql=True)
        return buffer.getvalue()

    def test_offline_script_can_be_generated_up_to_head(self):
        """오프라인 모드에서 죽는 리비전이 있으면 여기서 걸린다.

        오프라인의 connection.execute()는 None을 돌려주므로, 조회 결과를 읽는 코드
        (중복·고아 참조 검사 같은 것)를 그대로 두면 AttributeError로 죽는다.
        온라인 테스트만으로는 드러나지 않는다.
        """
        sql = self._offline_sql(f"{SCHEMA_CHANGE}:head")
        self.assertIn("uq_chat_rooms_free_talk", sql)

    def test_free_talk_index_is_partial_on_postgresql(self):
        """WHERE가 빠지면 시나리오 방까지 하나로 묶여 운영에서 방 생성이 막힌다.

        SQLite 테스트로는 잡히지 않는다. `sqlite_where`만 주고 `postgresql_where`를
        빠뜨려도 개발 환경은 멀쩡하기 때문이다. PostgreSQL DDL을 직접 확인한다.
        """
        sql = self._offline_sql(f"{SCHEMA_CHANGE}:head")
        create = next(
            line for line in sql.splitlines() if "uq_chat_rooms_free_talk" in line
        )
        self.assertIn("UNIQUE INDEX", create)
        self.assertIn("WHERE scenario_id IS NULL", create)

    def test_seed_inserts_render_actual_values(self):
        """파라미터가 바인딩되지 않으면 모든 값이 NULL로 렌더된다.

        "NULL, NULL"로는 판별할 수 없다. roleplay 시드는 time_context·place_context가
        둘 다 정당한 NULL이라 그 부분 문자열이 정상 스크립트에도 나온다. 대신 첫 컬럼을
        본다. 시드의 첫 컬럼은 id(또는 persona_id)이고 어떤 시드에서도 NULL이 아니므로,
        `VALUES (NULL`은 바인딩이 통째로 빠졌을 때만 나온다.
        """
        sql = self._offline_sql(f"{SCHEMA_CHANGE}:head")

        inserts = [line for line in sql.splitlines() if line.startswith("INSERT INTO")]
        self.assertTrue(inserts)
        for statement in inserts:
            with self.subTest(statement=statement[:60]):
                self.assertNotIn("VALUES (NULL", statement)

    def test_catalog_seed_values_appear_in_the_script(self):
        """NULL이 아니라는 것만으로는 부족하다. 시드 상수의 값이 그대로 실려야 한다."""
        sql = self._offline_sql(f"{SCHEMA_CHANGE}:{CATALOG}")
        self.assertIn("'doyun'", sql)
        self.assertIn("'interview'", sql)
        self.assertIn("'roleplay'", sql)

    def test_campus_directions_values_appear_in_the_script(self):
        sql = self._offline_sql(f"{PROGRESS}:{CAMPUS_DIRECTIONS}")
        self.assertIn("'campus_directions'", sql)
        self.assertIn("'doyun'", sql)


class CampusDirectionsRevisionTests(MigrationTestCase):
    """campus_directions 시나리오 시드 (d5b8c07f9a13)."""

    def _revision_module(self):
        """시드 값의 출처는 리비전 상수뿐이다. 테스트가 값을 따로 적으면 두 곳이 어긋난다."""
        import importlib.util

        path = next(
            (PROJECT_ROOT / "migrations" / "versions").glob(f"{CAMPUS_DIRECTIONS}_*.py")
        )
        spec = importlib.util.spec_from_file_location("campus_revision", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_scenario_row_matches_revision_constants(self):
        """INSERT가 시드 상수를 빠짐없이 반영하는지 본다.

        상수 값 자체가 옳은지는 검증하지 않는다(기획 판단이라 테스트가 정할 수 없다).
        기대값을 상수에서 가져오므로 상수를 고치면 양쪽이 함께 움직인다. 이 테스트가
        실제로 막는 것은 INSERT문이 컬럼을 빠뜨리는 경우이며, 그때 실패한다.
        """
        seed = self._revision_module().SCENARIO_SEED
        self.upgrade(CAMPUS_DIRECTIONS)

        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT description, time_context, place_context, communication_goal,"
                    "       end_condition, max_turns, turn_limit_exit_line"
                    " FROM scenarios WHERE id = :id"
                ),
                {"id": seed["id"]},
            ).one()

        self.assertEqual(
            row._asdict(),
            {key: value for key, value in seed.items() if key != "id"},
        )

    def test_scenario_is_selectable_for_doyun(self):
        """매핑이 없으면 시나리오가 존재해도 사용자가 고를 수 없다."""
        module = self._revision_module()
        self.upgrade(CAMPUS_DIRECTIONS)

        with self.engine.connect() as connection:
            paired = connection.execute(
                text(
                    "SELECT COUNT(*) FROM persona_scenarios"
                    " WHERE persona_id = :persona_id AND scenario_id = :scenario_id"
                ),
                {"persona_id": module.PERSONA_ID, "scenario_id": module.SCENARIO_ID},
            ).scalar()
        self.assertEqual(paired, 1)

    def test_turn_limit_exit_line_is_filled_for_this_scenario(self):
        """턴 상한에서 대화를 매듭지을 말이 없으면 FAILED 종료를 만들 수 없다."""
        module = self._revision_module()
        self.upgrade(CAMPUS_DIRECTIONS)

        with self.engine.connect() as connection:
            line = connection.execute(
                text("SELECT turn_limit_exit_line FROM scenarios WHERE id = :id"),
                {"id": module.SCENARIO_ID},
            ).scalar()
        self.assertTrue(line)

    def test_existing_scenarios_keep_null_exit_line(self):
        """기존 시나리오에는 전용 마무리 대사가 없다. 억지로 채우지 않는다."""
        self.upgrade(CAMPUS_DIRECTIONS)

        with self.engine.connect() as connection:
            nulls = connection.execute(
                text(
                    "SELECT COUNT(*) FROM scenarios"
                    " WHERE id IN ('interview', 'roleplay')"
                    "   AND turn_limit_exit_line IS NULL"
                )
            ).scalar()
        self.assertEqual(nulls, 2)

    def test_failed_status_is_accepted_by_check_constraint(self):
        """CHECK 목록에 failed가 빠지면 시나리오 실패를 저장할 수 없다."""
        self.upgrade(CAMPUS_DIRECTIONS)

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_rooms"
                    " (id, user_id, persona_id, name, created_at, updated_at,"
                    "  last_message_at, status, turn_count)"
                    " VALUES ('r-failed', 'u1', 'doyun', '방', :now, :now, :now,"
                    "  'failed', 10)"
                ),
                {"now": "2026-08-08 00:00:00"},
            )

    def test_downgrade_removes_scenario_and_mapping(self):
        module = self._revision_module()
        self.upgrade(CAMPUS_DIRECTIONS)
        self.downgrade(PROGRESS)

        with self.engine.connect() as connection:
            scenarios = set(connection.execute(text("SELECT id FROM scenarios")).scalars())
            pairs = set(
                connection.execute(
                    text("SELECT scenario_id FROM persona_scenarios")
                ).scalars()
            )
        self.assertNotIn(module.SCENARIO_ID, scenarios)
        self.assertNotIn(module.SCENARIO_ID, pairs)
        self.assertNotIn("turn_limit_exit_line", self.columns("scenarios"))

    def test_upgrade_downgrade_upgrade_is_repeatable(self):
        self.upgrade(CAMPUS_DIRECTIONS)
        self.downgrade(PROGRESS)
        self.upgrade(CAMPUS_DIRECTIONS)

        with self.engine.connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM scenarios WHERE id = 'campus_directions'")
            ).scalar()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
