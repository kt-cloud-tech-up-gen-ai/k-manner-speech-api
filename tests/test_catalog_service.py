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

from app.core.db import Base
from app.services import catalog
from tests.catalog_fixtures import link, make_persona, make_scenario, seed_catalog

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

    def test_is_paired_answers_for_the_seeded_combination(self):
        with self.Session() as session:
            session.add(make_scenario("unpaired", description="매핑하지 않음"))
            session.commit()

            self.assertTrue(catalog.is_paired(session, "doyun", "interview"))
            self.assertFalse(catalog.is_paired(session, "doyun", "unpaired"))

    def test_is_paired_normalizes_like_the_find_functions(self):
        """find_*와 같은 규칙으로 받아야 한다.

        한쪽만 관대하면 존재 검사는 통과하고 조합 검사는 실패해, 멀쩡한 조합이 400이 된다.
        현재 라우터는 이미 정규화된 id를 넘기므로 이 테스트가 유일한 감시자다.
        """
        with self.Session() as session:
            self.assertTrue(catalog.is_paired(session, "  DOYUN  ", "Interview"))

    def test_is_paired_is_false_for_unknown_ids(self):
        with self.Session() as session:
            self.assertFalse(catalog.is_paired(session, "ghost", "interview"))
            self.assertFalse(catalog.is_paired(session, "doyun", "ghost"))

    def test_entities_satisfy_both_summary_and_detail_dtos(self):
        """DTO가 요구하는 값이 DB에서 그대로 나와야 한다."""
        from app.schemas.catalog import (
            PersonaResponse,
            PersonaSummaryResponse,
            ScenarioResponse,
            ScenarioSummaryResponse,
        )

        with self.Session() as session:
            persona = catalog.find_persona(session, "doyun")
            scenario = catalog.find_scenario(session, "interview")

            summary = PersonaSummaryResponse.model_validate(persona, from_attributes=True)
            self.assertEqual(summary.id, "doyun")
            self.assertEqual(summary.age, 22)

            detail = PersonaResponse.model_validate(persona, from_attributes=True)
            self.assertTrue(detail.relationship_description)
            self.assertIsNotNone(detail.version)

            scenario_summary = ScenarioSummaryResponse.model_validate(
                scenario, from_attributes=True
            )
            self.assertEqual(scenario_summary.place_context, "회사 회의실")
            self.assertEqual(scenario_summary.title_ko, "면접 상황 대화 연습")
            self.assertEqual(
                scenario_summary.communication_goal,
                "면접관의 질문에 존댓말로 끝까지 답한다",
            )

            scenario_detail = ScenarioResponse.model_validate(
                scenario, from_attributes=True
            )
            self.assertEqual(scenario_detail.max_turns, 20)
            self.assertTrue(scenario_detail.communication_goal)
            self.assertTrue(scenario_detail.end_condition)

    def test_summary_dto_hides_prompt_internals(self):
        """프롬프트 규칙이 바뀌어도 목록 계약이 흔들리지 않아야 한다."""
        from app.schemas.catalog import PersonaSummaryResponse, ScenarioSummaryResponse

        self.assertNotIn(
            "relationship_description", PersonaSummaryResponse.model_fields
        )
        for field in ("end_condition", "max_turns"):
            with self.subTest(field=field):
                self.assertNotIn(field, ScenarioSummaryResponse.model_fields)

    def test_summary_dto_has_no_embed(self):
        """요약에 상대쪽 목록이 실리면 목록 응답이 N+1 조회로 부풀고 서로를 참조한다."""
        from app.schemas.catalog import PersonaSummaryResponse, ScenarioSummaryResponse

        self.assertNotIn("scenarios", PersonaSummaryResponse.model_fields)
        self.assertNotIn("personas", ScenarioSummaryResponse.model_fields)

    def test_detail_dto_embeds_only_summaries(self):
        """상세를 임베드하면 응답이 서로를 물고 부풀어난다. 요약만 담아야 한다."""
        from typing import get_args

        from app.schemas.catalog import (
            PersonaResponse,
            PersonaSummaryResponse,
            ScenarioResponse,
            ScenarioSummaryResponse,
        )

        def embedded_model(model, field):
            return get_args(model.model_fields[field].annotation)[0]

        self.assertIs(
            embedded_model(PersonaResponse, "scenarios"), ScenarioSummaryResponse
        )
        self.assertIs(
            embedded_model(ScenarioResponse, "personas"), PersonaSummaryResponse
        )

    def test_persona_detail_dto_carries_linked_scenarios(self):
        from app.schemas.catalog import PersonaResponse

        with self.Session() as session:
            session.add(make_scenario("cafe", description="카페 주문"))
            session.commit()
            link(session, "doyun", "cafe")

            detail = PersonaResponse.model_validate(
                catalog.find_persona(session, "doyun"), from_attributes=True
            )
        self.assertEqual([s.id for s in detail.scenarios], ["cafe", "interview"])

    def test_scenario_detail_dto_carries_linked_personas(self):
        from app.schemas.catalog import ScenarioResponse

        with self.Session() as session:
            session.add(make_persona("ahn", first_name="안"))
            session.commit()
            link(session, "ahn", "interview")

            detail = ScenarioResponse.model_validate(
                catalog.find_scenario(session, "interview"), from_attributes=True
            )
        self.assertEqual([p.id for p in detail.personas], ["ahn", "doyun"])

    def test_detail_dto_allows_empty_embed(self):
        """조합이 없는 것은 오류가 아니다. 고를 수 있는 상황이 아직 없다는 뜻이다."""
        from app.schemas.catalog import PersonaResponse

        with self.Session() as session:
            session.add(make_persona("mina", first_name="미나"))
            session.commit()

            detail = PersonaResponse.model_validate(
                catalog.find_persona(session, "mina"), from_attributes=True
            )
        self.assertEqual(detail.scenarios, [])


if __name__ == "__main__":
    unittest.main()
