"""personas / scenarios 스키마 계약 테스트 (plan-acc KAN-16 T1)."""

import unittest

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.catalog_fixtures import make_persona, make_scenario

from app.core.db import Base
from app.models.catalog import Persona, Scenario
from app.models.user import Gender

# (컬럼명: (타입 문자열, nullable))
EXPECTED_PERSONA_COLUMNS = {
    "id": ("VARCHAR(64)", False),
    "first_name": ("VARCHAR(64)", False),
    "middle_name": ("VARCHAR(64)", True),
    "last_name": ("VARCHAR(64)", True),
    "age": ("INTEGER", False),
    "gender": ("VARCHAR(32)", False),
    "description": ("TEXT", False),
    "relationship_description": ("TEXT", False),
    "voice_id": ("VARCHAR(64)", True),
    "version": ("DATETIME", False),
}

EXPECTED_SCENARIO_COLUMNS = {
    "id": ("VARCHAR(64)", False),
    "description": ("TEXT", False),
    "time_context": ("TEXT", True),
    "place_context": ("TEXT", True),
    "communication_goal": ("TEXT", False),
    "end_condition": ("TEXT", False),
    "max_turns": ("INTEGER", False),
    "version": ("DATETIME", False),
}


class SchemaContractTests(unittest.TestCase):
    def _assert_columns(self, model, expected):
        columns = model.__table__.columns
        self.assertEqual(set(columns.keys()), set(expected))
        for name, (type_str, nullable) in expected.items():
            with self.subTest(table=model.__tablename__, column=name):
                column = columns[name]
                self.assertEqual(str(column.type).upper(), type_str)
                self.assertEqual(column.nullable, nullable)

    def test_persona_columns_match_agreed_schema(self):
        self._assert_columns(Persona, EXPECTED_PERSONA_COLUMNS)

    def test_scenario_columns_match_agreed_schema(self):
        self._assert_columns(Scenario, EXPECTED_SCENARIO_COLUMNS)

    def test_ids_are_primary_keys(self):
        self.assertEqual([c.name for c in Persona.__table__.primary_key], ["id"])
        self.assertEqual([c.name for c in Scenario.__table__.primary_key], ["id"])

    def test_id_width_matches_chat_rooms_reference_columns(self):
        """T3에서 FK를 걸려면 참조 컬럼과 폭이 같아야 한다."""
        from app.models.chat import ChatRoom

        room_columns = ChatRoom.__table__.columns
        self.assertEqual(
            str(Persona.__table__.c.id.type), str(room_columns["persona_id"].type)
        )
        self.assertEqual(
            str(Scenario.__table__.c.id.type), str(room_columns["scenario_id"].type)
        )


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def test_tables_are_created(self):
        table_names = set(inspect(self.engine).get_table_names())
        self.assertIn("personas", table_names)
        self.assertIn("scenarios", table_names)

    def test_persona_roundtrip_with_full_profile(self):
        with self.Session() as session:
            session.add(
                Persona(
                    id="doyun",
                    first_name="도윤",
                    middle_name=None,
                    last_name="김",
                    age=27,
                    gender=Gender.MALE,
                    description="다정한 말투의 대화 상대",
                    relationship_description="같은 학교 선배",
                    voice_id="v-1",
                )
            )
            session.commit()

            saved = session.get(Persona, "doyun")
            self.assertEqual(saved.last_name, "김")
            self.assertEqual(saved.age, 27)
            self.assertEqual(saved.gender, Gender.MALE)
            self.assertEqual(saved.relationship_description, "같은 학교 선배")
            self.assertEqual(saved.voice_id, "v-1")

    def test_persona_optional_fields_default_to_null(self):
        """선택값은 middle_name·last_name·voice_id 셋뿐이다."""
        with self.Session() as session:
            session.add(
                make_persona(
                    "minimal", middle_name=None, last_name=None, voice_id=None
                )
            )
            session.commit()

            saved = session.get(Persona, "minimal")
            for field in ("middle_name", "last_name", "voice_id"):
                with self.subTest(field=field):
                    self.assertIsNone(getattr(saved, field))

    def test_persona_required_fields_reject_null(self):
        """말투·호칭을 정하는 값이 비면 프롬프트를 만들 수 없으므로 DB가 막는다."""
        for field in ("first_name", "age", "gender", "description",
                      "relationship_description"):
            with self.subTest(field=field):
                with self.Session() as session:
                    session.add(make_persona(f"broken-{field}", **{field: None}))
                    with self.assertRaises(IntegrityError):
                        session.commit()

    def test_scenario_required_fields_reject_null(self):
        """목표·종료조건·턴 상한이 없으면 시나리오가 성립하지 않는다."""
        for field in ("description", "communication_goal", "end_condition", "max_turns"):
            with self.subTest(field=field):
                with self.Session() as session:
                    session.add(make_scenario(f"broken-{field}", **{field: None}))
                    with self.assertRaises(IntegrityError):
                        session.commit()

    def _version_roundtrip(self, entity):
        with self.Session() as session:
            session.add(entity)
            session.commit()
            first_version = entity.version
            self.assertIsNotNone(first_version)

            entity.description = "정의 수정"
            session.commit()

        self.assertGreater(entity.version, first_version)

    def test_persona_version_is_filled_on_insert_and_bumped_on_update(self):
        self._version_roundtrip(make_persona())

    def test_scenario_version_is_filled_on_insert_and_bumped_on_update(self):
        self._version_roundtrip(make_scenario())

    def test_gender_rejects_value_outside_enum(self):
        with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO personas"
                        " (id, first_name, age, gender, description,"
                        "  relationship_description, version)"
                        " VALUES ('bad', '이름', 22, 'alien', '설명', '선배', :now)"
                    ),
                    {"now": "2026-08-07 00:00:00"},
                )

    def test_scenario_roundtrip_with_full_context(self):
        with self.Session() as session:
            session.add(
                make_scenario(
                    time_context="평일 오전 10시",
                    place_context="회사 회의실",
                    communication_goal="자기소개를 존댓말로 끝까지 마친다",
                    end_condition="면접관이 마무리 인사를 하면 종료",
                    max_turns=20,
                )
            )
            session.commit()

            saved = session.get(Scenario, "interview")
            self.assertEqual(saved.time_context, "평일 오전 10시")
            self.assertEqual(saved.place_context, "회사 회의실")
            self.assertEqual(saved.communication_goal, "자기소개를 존댓말로 끝까지 마친다")
            self.assertEqual(saved.end_condition, "면접관이 마무리 인사를 하면 종료")
            self.assertEqual(saved.max_turns, 20)

    def test_scenario_background_fields_may_be_null(self):
        """시간·공간은 배경 묘사라 없어도 시나리오가 성립한다."""
        with self.Session() as session:
            session.add(make_scenario("minimal", time_context=None, place_context=None))
            session.commit()

            saved = session.get(Scenario, "minimal")
            self.assertIsNone(saved.time_context)
            self.assertIsNone(saved.place_context)

    def test_duplicate_persona_id_is_rejected(self):
        with self.Session() as session:
            session.add(make_persona())
            session.commit()

        with self.Session() as session:
            with self.assertRaises(IntegrityError):
                session.execute(
                    text(
                        "INSERT INTO personas"
                        " (id, first_name, age, gender, description,"
                        "  relationship_description, version)"
                        " VALUES ('doyun', '도윤', 22, 'male', '중복', '또래', :now)"
                    ),
                    {"now": "2026-08-07 00:00:00"},
                )
                session.commit()


if __name__ == "__main__":
    unittest.main()
