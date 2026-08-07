"""테스트용 카탈로그 시드.

운영 시드는 마이그레이션 리비전(`9c1f4b0a7d52`)이 넣는다. 테스트는 마이그레이션을 돌리지
않고 create_all로 스키마만 만들기 때문에, API가 기대하는 최소 카탈로그를 여기서 채운다.

id는 마이그레이션 시드와 같은 값을 쓴다. 두 곳이 어긋나면
`tests/test_migrations.py::test_seed_matches_revision_constants`가 아니라
API 테스트가 먼저 깨지므로, id를 바꿀 때는 양쪽을 함께 고쳐야 한다.
"""

from sqlalchemy.orm import Session

from app.models.catalog import Persona, Scenario
from app.models.user import Gender

PERSONA_ID = "doyun"
SCENARIO_ID = "interview"


def make_persona(persona_id: str = PERSONA_ID, **overrides) -> Persona:
    """NOT NULL 컬럼을 모두 채운 Persona. 테스트는 관심 있는 값만 덮어쓴다."""
    values = {
        "id": persona_id,
        "first_name": "도윤",
        "age": 22,
        "gender": Gender.MALE,
        "description": "도윤 / 캠퍼스 훈남 / 처음 만난 또래",
        "relationship_description": "같은 캠퍼스에서 오늘 처음 만난 또래",
        "voice_id": None,
    }
    values.update(overrides)
    return Persona(**values)


def make_scenario(scenario_id: str = SCENARIO_ID, **overrides) -> Scenario:
    """NOT NULL 컬럼을 모두 채운 Scenario."""
    values = {
        "id": scenario_id,
        "description": "면접 상황 대화 연습",
        "time_context": "평일 오전",
        "place_context": "회사 회의실",
        "communication_goal": "면접관의 질문에 존댓말로 끝까지 답한다",
        "end_condition": "면접관이 마무리 인사를 하면 종료",
        "max_turns": 20,
    }
    values.update(overrides)
    return Scenario(**values)


def seed_catalog(session: Session) -> None:
    session.add(make_persona())
    session.add(make_scenario())
    session.commit()
