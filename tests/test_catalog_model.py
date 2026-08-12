"""personas / scenarios 스키마 계약 테스트 (plan-acc KAN-16 T1)."""

import unittest

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.catalog import Persona, Scenario, persona_scenarios
from app.models.user import Gender
from tests.catalog_fixtures import make_persona, make_scenario

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
    "headline": ("VARCHAR(120)", True),
    "avatar_url": ("TEXT", True),
    "sort_order": ("INTEGER", False),
    "is_active": ("BOOLEAN", False),
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
    "turn_limit_exit_line": ("TEXT", True),
    "title_ko": ("VARCHAR(160)", False),
    "title_en": ("VARCHAR(160)", True),
    "difficulty": ("VARCHAR(16)", True),
    "estimated_minutes": ("SMALLINT", True),
    "is_featured": ("BOOLEAN", False),
    "sort_order": ("INTEGER", False),
    "is_active": ("BOOLEAN", False),
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
                )
            )
            session.commit()

            saved = session.get(Persona, "doyun")
            self.assertEqual(saved.last_name, "김")
            self.assertEqual(saved.age, 27)
            self.assertEqual(saved.gender, Gender.MALE)
            self.assertEqual(saved.relationship_description, "같은 학교 선배")

    def test_persona_optional_fields_default_to_null(self):
        """선택값인 middle_name·last_name은 NULL로 저장할 수 있다."""
        with self.Session() as session:
            session.add(
                make_persona("minimal", middle_name=None, last_name=None)
            )
            session.commit()

            saved = session.get(Persona, "minimal")
            for field in ("middle_name", "last_name"):
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
        """enum_column의 CHECK 제약이 DB 계층에서 막는다."""
        with self.Session() as session:
            session.add(make_persona("bad", gender="alien"))
            with self.assertRaises(IntegrityError):
                session.commit()

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
        """id는 자연키다. 같은 id로 두 번 넣으면 PK 제약이 막는다.

        세션을 새로 열어야 한다. 같은 세션에서 두 번 add하면 identity map이 두 객체를
        하나로 합쳐 버려 INSERT가 애초에 두 번 나가지 않는다.
        """
        with self.Session() as session:
            session.add(make_persona())
            session.commit()

        with self.Session() as session:
            session.add(make_persona(description="중복"))
            with self.assertRaises(IntegrityError):
                session.commit()


class MappingSchemaContractTests(unittest.TestCase):
    """persona_scenarios 스키마 계약 (plan-acc 2026-08-08 T1)."""

    def test_columns_match_catalog_id_width(self):
        columns = persona_scenarios.columns
        self.assertEqual(set(columns.keys()), {"persona_id", "scenario_id"})
        for name in ("persona_id", "scenario_id"):
            with self.subTest(column=name):
                self.assertEqual(str(columns[name].type).upper(), "VARCHAR(64)")
                self.assertFalse(columns[name].nullable)

    def test_primary_key_is_the_pair(self):
        """조합 자체가 키다. 같은 조합을 두 번 넣을 수 없다."""
        self.assertEqual(
            [c.name for c in persona_scenarios.primary_key],
            ["persona_id", "scenario_id"],
        )

    def test_foreign_keys_restrict_catalog_deletion(self):
        targets = {
            fk.parent.name: (fk.column.table.name, fk.ondelete)
            for fk in persona_scenarios.foreign_keys
        }
        self.assertEqual(targets["persona_id"], ("personas", "RESTRICT"))
        self.assertEqual(targets["scenario_id"], ("scenarios", "RESTRICT"))

    def test_both_directions_declare_id_ordering(self):
        """양쪽 관계가 ORDER BY를 발행하도록 선언되어 있어야 한다.

        결과 리스트의 순서만 보는 테스트로는 이 계약을 지킬 수 없다. order_by를 지워도
        SQLite는 복합 PK 커버링 인덱스를 타면서 우연히 id 순서로 행을 돌려주기 때문에
        초록불이 유지된다. 그 경우 운영 DB(PostgreSQL)에서 순서가 깨져도 CI는 조용하다.
        정렬을 결정하는 것은 relationship 선언이므로 선언을 직접 단언한다.
        """
        def declared_ordering(relationship_attribute) -> list[str]:
            # 정렬을 선언하지 않으면 order_by는 시퀀스가 아니라 False다.
            return [str(column) for column in relationship_attribute.property.order_by or ()]

        self.assertEqual(declared_ordering(Persona.scenarios), ["scenarios.id"])
        self.assertEqual(declared_ordering(Scenario.personas), ["personas.id"])


class MappingPersistenceTests(unittest.TestCase):
    """persona ↔ scenario N:N 동작 (plan-acc 2026-08-08 T1).

    SQLite는 기본적으로 FK를 강제하지 않으므로 연결마다 PRAGMA를 켠다
    (tests/test_chatroom_model.py::ForeignKeyTests와 같은 방식).
    """

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        event.listen(self.engine, "connect", self._enable_foreign_keys)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

        with self.Session() as session:
            session.add(make_persona("doyun"))
            session.add(make_persona("mina", first_name="미나", gender=Gender.FEMALE))
            session.add(make_scenario("interview"))
            session.add(make_scenario("roleplay", description="역할극"))
            session.commit()

    def tearDown(self):
        event.remove(self.engine, "connect", self._enable_foreign_keys)
        Base.metadata.drop_all(bind=self.engine)

    @staticmethod
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def _link(self, persona_id: str, scenario_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                persona_scenarios.insert().values(
                    persona_id=persona_id, scenario_id=scenario_id
                )
            )

    def test_table_is_created(self):
        self.assertIn("persona_scenarios", inspect(self.engine).get_table_names())

    def test_persona_exposes_linked_scenarios(self):
        self._link("doyun", "interview")

        with self.Session() as session:
            persona = session.get(Persona, "doyun")
            self.assertEqual([s.id for s in persona.scenarios], ["interview"])

    def test_scenario_exposes_linked_personas(self):
        self._link("doyun", "interview")

        with self.Session() as session:
            scenario = session.get(Scenario, "interview")
            self.assertEqual([p.id for p in scenario.personas], ["doyun"])

    def test_relationship_is_many_to_many_in_both_directions(self):
        """한 상대가 여러 상황을, 한 상황이 여러 상대를 가질 수 있다."""
        self._link("doyun", "interview")
        self._link("doyun", "roleplay")
        self._link("mina", "interview")

        with self.Session() as session:
            self.assertEqual(
                [s.id for s in session.get(Persona, "doyun").scenarios],
                ["interview", "roleplay"],
            )
            self.assertEqual(
                [p.id for p in session.get(Scenario, "interview").personas],
                ["doyun", "mina"],
            )

    def test_linked_lists_come_back_in_id_order(self):
        """상세 응답의 순서가 목록 API와 같도록 id 오름차순으로 고정한다.

        정렬 선언 자체는 test_both_directions_declare_id_ordering이 지킨다. 이 테스트는
        선언이 실제 조회 결과에 반영되는지만 본다(삽입 순서와 id 순서를 어긋나게 넣는다).
        """
        self._link("doyun", "roleplay")
        self._link("doyun", "interview")

        with self.Session() as session:
            self.assertEqual(
                [s.id for s in session.get(Persona, "doyun").scenarios],
                ["interview", "roleplay"],
            )

    def test_persona_without_mapping_has_empty_list(self):
        """매핑이 없으면 빈 목록이다(오류가 아니다)."""
        with self.Session() as session:
            self.assertEqual(session.get(Persona, "mina").scenarios, [])

    def test_linking_one_side_updates_the_other_before_flush(self):
        """back_populates: 한쪽에 연결하면 반대쪽 컬렉션이 그 자리에서 따라온다.

        세션을 새로 열어 다시 조회하는 테스트로는 이 계약을 지킬 수 없다. DB를 한 번
        왕복하면 매핑 행만으로 양쪽이 채워지므로, back_populates가 빠져도 결과가 같다.
        동기화가 깨지는 지점은 commit 이전의 같은 세션 안이다.
        """
        with self.Session() as session:
            persona = session.get(Persona, "doyun")
            scenario = session.get(Scenario, "interview")

            persona.scenarios.append(scenario)

            self.assertEqual([p.id for p in scenario.personas], ["doyun"])

    def test_relationship_write_creates_mapping_row(self):
        with self.Session() as session:
            persona = session.get(Persona, "doyun")
            persona.scenarios.append(session.get(Scenario, "interview"))
            session.commit()

        with self.engine.connect() as connection:
            rows = connection.execute(persona_scenarios.select()).all()
        self.assertEqual([tuple(row) for row in rows], [("doyun", "interview")])

    def test_unknown_persona_is_rejected(self):
        with self.assertRaises(IntegrityError):
            self._link("ghost", "interview")

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaises(IntegrityError):
            self._link("doyun", "ghost")

    def test_duplicate_pair_is_rejected(self):
        self._link("doyun", "interview")
        with self.assertRaises(IntegrityError):
            self._link("doyun", "interview")

    def _delete_row(self, model, row_id: str) -> None:
        """세션(unit of work)을 거치지 않고 행 하나를 지운다.

        ORM 경로(`session.delete(persona)`)로는 이 제약을 확인할 수 없다. SQLAlchemy가
        secondary 행을 먼저 정리하고 나서 카탈로그 행을 지우기 때문이다. RESTRICT는
        DB 계층 제약이므로 DELETE를 그대로 보내야 걸린다.
        """
        with self.engine.begin() as connection:
            connection.execute(model.__table__.delete().where(model.id == row_id))

    def test_persona_referenced_by_mapping_cannot_be_deleted(self):
        """RESTRICT: 매핑이 남아 있으면 카탈로그 행을 지울 수 없다."""
        self._link("doyun", "interview")

        with self.assertRaises(IntegrityError):
            self._delete_row(Persona, "doyun")

    def test_scenario_referenced_by_mapping_cannot_be_deleted(self):
        self._link("doyun", "interview")

        with self.assertRaises(IntegrityError):
            self._delete_row(Scenario, "interview")

    def test_removing_link_through_relationship_deletes_mapping_row(self):
        """매핑을 먼저 끊으면 카탈로그 행을 지울 수 있다(RESTRICT의 정상 경로)."""
        self._link("doyun", "interview")

        with self.Session() as session:
            persona = session.get(Persona, "doyun")
            persona.scenarios.remove(session.get(Scenario, "interview"))
            session.commit()

        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(persona_scenarios.select()).all(), [])


if __name__ == "__main__":
    unittest.main()
