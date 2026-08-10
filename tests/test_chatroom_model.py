"""ChatRoom 스키마 계약 테스트 (plan-acc T2)."""

import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.catalog import Persona
from app.models.chat import ChatRoom, ChatRoomStatus
from tests.catalog_fixtures import seed_catalog

# (컬럼명, python 타입 문자열, nullable)
EXPECTED_COLUMNS = {
    "id": ("VARCHAR(32)", False),
    "user_id": ("VARCHAR(128)", False),
    "persona_id": ("VARCHAR(64)", False),
    "scenario_id": ("VARCHAR(64)", True),
    "name": ("VARCHAR(200)", False),
    "created_at": ("DATETIME", False),
    "updated_at": ("DATETIME", False),
    "last_message_at": ("DATETIME", False),
    "last_message_preview": ("VARCHAR(100)", True),
    "last_read_at": ("DATETIME", True),
    "status": ("VARCHAR(32)", False),
    "turn_count": ("INTEGER", False),
}


class SchemaContractTests(unittest.TestCase):
    def test_columns_match_agreed_schema(self):
        columns = ChatRoom.__table__.columns
        self.assertEqual(set(columns.keys()), set(EXPECTED_COLUMNS))
        for name, (type_str, nullable) in EXPECTED_COLUMNS.items():
            with self.subTest(column=name):
                column = columns[name]
                self.assertEqual(str(column.type).upper(), type_str, name)
                self.assertEqual(column.nullable, nullable, name)

    def test_last_message_at_index_exists(self):
        index_names = {index.name for index in ChatRoom.__table__.indexes}
        self.assertIn("ix_chat_rooms_user_id_last_message_at", index_names)

    def test_status_covers_the_agreed_states(self):
        self.assertEqual(
            [status.value for status in ChatRoomStatus],
            ["in_progress", "completed", "failed", "abandoned"],
        )

    def test_status_is_stored_as_lowercase_value(self):
        """DB에 저장되는 문자열은 멤버 이름(ABANDONED)이 아니라 값(abandoned)이어야 한다.

        이 문자열은 CHECK 제약과 마이그레이션 시드가 직접 쓰는 값이고, API 요청/응답에도
        그대로 실린다.

        저장했다가 읽어서 비교하는 방식으로는 검증할 수 없다. 컬럼 타입이 읽을 때 값을 다시
        enum으로 되돌리는 데다 ChatRoomStatus가 str Enum이라, 멤버 이름으로 저장되는 회귀가
        나도 `== "abandoned"` 비교는 그대로 통과한다. 저장 어휘를 정하는 것은 타입이므로
        타입을 직접 단언한다.
        """
        self.assertEqual(
            ChatRoom.__table__.c.status.type.enums,
            [status.value for status in ChatRoomStatus],
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

    def _add_room(self, session, **overrides):
        room = ChatRoom(
            user_id="user-1", persona_id="doyun", name="도윤과의 대화", **overrides
        )
        session.add(room)
        session.commit()
        return room

    def test_timestamps_are_filled_on_insert(self):
        with self.Session() as session:
            room = self._add_room(session)

        self.assertIsNotNone(room.created_at)
        self.assertIsNotNone(room.updated_at)
        self.assertEqual(room.last_message_at, room.created_at)
        self.assertIsNone(room.last_message_preview)
        self.assertIsNone(room.last_read_at)

    def test_updating_name_touches_updated_at_only(self):
        with self.Session() as session:
            room = self._add_room(session)
            created_at, updated_at, last_message_at = (
                room.created_at,
                room.updated_at,
                room.last_message_at,
            )

            room.name = "새 이름"
            session.commit()

        self.assertGreater(room.updated_at, updated_at)
        self.assertEqual(room.created_at, created_at)
        self.assertEqual(room.last_message_at, last_message_at)

    def test_name_is_required(self):
        with self.Session() as session:
            session.add(ChatRoom(user_id="user-1", persona_id="doyun", name=None))
            with self.assertRaises(IntegrityError):
                session.commit()


class ForeignKeyTests(unittest.TestCase):
    """persona_id / scenario_id의 카탈로그 참조 무결성 (plan-acc KAN-16 T3).

    SQLite는 기본적으로 FK를 강제하지 않으므로 연결마다 PRAGMA를 켠다.
    """

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        event.listen(self.engine, "connect", self._enable_foreign_keys)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

        with self.Session() as session:
            seed_catalog(session)

    def tearDown(self):
        event.remove(self.engine, "connect", self._enable_foreign_keys)
        Base.metadata.drop_all(bind=self.engine)

    @staticmethod
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_declared_foreign_keys_point_at_catalog(self):
        targets = {
            fk.parent.name: (fk.column.table.name, fk.ondelete)
            for fk in ChatRoom.__table__.foreign_keys
        }
        self.assertEqual(targets["persona_id"], ("personas", "RESTRICT"))
        self.assertEqual(targets["scenario_id"], ("scenarios", "RESTRICT"))

    def test_user_id_has_no_foreign_key(self):
        """Supabase auth.users는 다른 스키마라 FK를 걸지 않는다(논리 참조)."""
        self.assertEqual(
            [fk.parent.name for fk in ChatRoom.__table__.foreign_keys if fk.parent.name == "user_id"],
            [],
        )

    def test_known_persona_and_scenario_are_accepted(self):
        with self.Session() as session:
            session.add(
                ChatRoom(
                    user_id="u1", persona_id="doyun", scenario_id="interview", name="방"
                )
            )
            session.commit()

    def test_scenario_id_may_be_null(self):
        with self.Session() as session:
            session.add(ChatRoom(user_id="u1", persona_id="doyun", name="방"))
            session.commit()

    def test_unknown_persona_is_rejected(self):
        with self.Session() as session:
            session.add(ChatRoom(user_id="u1", persona_id="ghost", name="방"))
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_unknown_scenario_is_rejected(self):
        with self.Session() as session:
            session.add(
                ChatRoom(
                    user_id="u1", persona_id="doyun", scenario_id="ghost", name="방"
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_deleting_referenced_persona_is_restricted(self):
        """RESTRICT: 방이 참조하는 동안에는 persona 행을 지울 수 없다.

        `DELETE FROM personas`를 그대로 보내는 방식으로는 이 계약을 지킬 수 없다.
        seed_catalog가 persona_scenarios 매핑 행(doyun↔interview)도 함께 넣기 때문에,
        chat_rooms의 FK를 통째로 지워도 매핑 테이블의 RESTRICT가 대신 DELETE를 막아
        초록불이 유지된다(그쪽은 test_catalog_model.py가 따로 지킨다).

        session.delete는 매핑 행을 먼저 정리하고 나서 personas를 지운다. 그래서 남아서
        DELETE를 막는 것은 chat_rooms → personas FK 하나뿐이고, 그것이 이 테스트가
        확인하려는 제약이다.

        전제: Persona에서 ChatRoom으로 가는 ORM 관계가 없다. 그 관계를 추가하면
        session.delete가 참조하는 방까지 손대기 때문에 이 테스트가 헛되이 빨간불이 된다
        (제약은 멀쩡한데 IntegrityError가 안 난다). 그때는 방을 지우는 대신
        DELETE 문을 직접 보내되, 위에서 말한 매핑 행 교란을 먼저 없애야 한다.
        """
        with self.Session() as session:
            session.add(ChatRoom(user_id="u1", persona_id="doyun", name="방"))
            session.commit()

        with self.Session() as session:
            session.delete(session.get(Persona, "doyun"))
            with self.assertRaises(IntegrityError):
                session.commit()


class ProgressTests(unittest.TestCase):
    """진행 상태·턴 수 컬럼 (plan-acc 2026-08-08 T2)."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _add_room(self, session, **overrides):
        room = ChatRoom(user_id="user-1", persona_id="doyun", name="방", **overrides)
        session.add(room)
        session.commit()
        return room

    def test_new_room_starts_in_progress_with_zero_turns(self):
        with self.Session() as session:
            room = self._add_room(session)

        self.assertEqual(room.status, ChatRoomStatus.IN_PROGRESS)
        self.assertEqual(room.turn_count, 0)

    def test_status_and_turn_count_survive_roundtrip(self):
        with self.Session() as session:
            room = self._add_room(session)
            room.turn_count = 3
            room.status = ChatRoomStatus.COMPLETED
            session.commit()
            room_id = room.id

        with self.Session() as session:
            saved = session.get(ChatRoom, room_id)
            self.assertEqual(saved.status, ChatRoomStatus.COMPLETED)
            self.assertEqual(saved.turn_count, 3)

    def test_status_rejects_value_outside_enum(self):
        """enum_column의 CHECK 제약이 DB 계층에서 막는다.

        SQLAlchemy는 enum 밖의 문자열을 그대로 DB에 보내므로 ORM 경로로도 제약에 닿는다.
        """
        with self.Session() as session:
            session.add(
                ChatRoom(user_id="u1", persona_id="doyun", name="방", status="done")
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_updating_progress_touches_updated_at(self):
        """진행 상태 변경도 방의 마지막 변경 시각에 반영된다."""
        with self.Session() as session:
            room = self._add_room(session)
            updated_at = room.updated_at

            room.turn_count = 1
            session.commit()

        self.assertGreater(room.updated_at, updated_at)


if __name__ == "__main__":
    unittest.main()
