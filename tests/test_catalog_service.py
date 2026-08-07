"""카탈로그 조회 서비스 (plan-acc KAN-16 T2).

이 파일이 규정하는 것:
- 목록·조회의 출처는 DB뿐이며 YAML을 읽지 않는다.
- id 조회는 대소문자·공백을 관대하게 받는다.
- 없는 id는 예외가 아니라 None으로 답한다(호출부가 400을 만들 수 있도록).
"""

import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.catalog_fixtures import make_persona, make_scenario, seed_catalog

from app.core.db import Base
from app.services import catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CatalogSourceTests(unittest.TestCase):
    def test_service_does_not_read_yaml(self):
        """카탈로그가 다시 파일을 읽기 시작하면 여기서 막는다."""
        source = (PROJECT_ROOT / "app" / "services" / "catalog.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("yaml", source)
        self.assertNotIn("prompt_builder", source)


class CatalogQueryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        with self.Session() as session:
            seed_catalog(session)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def test_lists_are_sorted_by_id(self):
        with self.Session() as session:
            session.add(make_persona("ahn", first_name="안"))
            session.add(make_scenario("cafe", description="카페 주문"))
            session.commit()

            self.assertEqual(
                [p.id for p in catalog.list_personas(session)], ["ahn", "doyun"]
            )
            self.assertEqual(
                [s.id for s in catalog.list_scenarios(session)], ["cafe", "interview"]
            )

    def test_empty_catalog_returns_empty_list(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        with self.Session() as session:
            self.assertEqual(catalog.list_personas(session), [])
            self.assertEqual(catalog.list_scenarios(session), [])

    def test_find_accepts_mixed_case_and_padding(self):
        with self.Session() as session:
            for raw in ("doyun", "DOYUN", "  Doyun  "):
                with self.subTest(raw=raw):
                    found = catalog.find_persona(session, raw)
                    self.assertIsNotNone(found)
                    self.assertEqual(found.id, "doyun")

            self.assertIsNotNone(catalog.find_scenario(session, " INTERVIEW "))

    def test_find_returns_none_for_unknown_id(self):
        with self.Session() as session:
            self.assertIsNone(catalog.find_persona(session, "ghost"))
            self.assertIsNone(catalog.find_scenario(session, "ghost"))

    def test_persona_carries_every_field_the_dto_exposes(self):
        """DTO가 요구하는 값이 DB에서 그대로 나와야 한다."""
        from app.schemas.catalog import PersonaItem, ScenarioItem

        with self.Session() as session:
            persona = catalog.find_persona(session, "doyun")
            scenario = catalog.find_scenario(session, "interview")

            item = PersonaItem.model_validate(persona, from_attributes=True)
            self.assertEqual(item.id, "doyun")
            self.assertEqual(item.age, 22)
            self.assertTrue(item.relationship_description)

            scenario_item = ScenarioItem.model_validate(scenario, from_attributes=True)
            self.assertEqual(scenario_item.max_turns, 20)
            self.assertTrue(scenario_item.communication_goal)
            self.assertTrue(scenario_item.end_condition)


if __name__ == "__main__":
    unittest.main()
