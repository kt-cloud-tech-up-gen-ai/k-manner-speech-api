"""ChatRoom 스키마 계약 테스트 (plan-acc T2)."""

import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.chat import ChatRoom

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

    def test_last_message_at_is_not_null_at_db_level(self):
        """ORM은 None을 '미지정'으로 보고 default를 채우므로 DB 제약을 직접 확인한다."""
        with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO chat_rooms "
                        "(id, user_id, persona_id, name, created_at, updated_at, last_message_at) "
                        "VALUES ('r1', 'u1', 'doyun', '방', :now, :now, NULL)"
                    ),
                    {"now": "2026-08-06 00:00:00"},
                )


if __name__ == "__main__":
    unittest.main()
