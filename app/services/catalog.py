"""persona / 시나리오 카탈로그 조회.

출처는 DB(`personas`, `scenarios`)다. 예전에는 프롬프트 YAML을 스캔해 목록을 만들었지만,
같은 값이 파일과 DB 두 곳에 존재하면 어느 쪽이 맞는지 알 수 없어 DB 하나로 모았다.

캐시는 두지 않는다. 카탈로그는 요청당 한 번 읽는 작은 테이블이고, 캐시를 두면
관리 API로 값을 고쳤을 때 프로세스마다 다른 값을 보게 된다.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Persona, Scenario, persona_scenarios


def canonical_id(raw: str) -> str:
    """클라이언트가 보낸 id를 카탈로그에 저장된 형태로 맞춘다.

    조회는 관대하게 받되(대소문자·앞뒤 공백), **저장은 반드시 이 값으로** 해야 한다.
    받은 값을 그대로 chat_rooms에 넣으면 조회는 통과하고 FK는 위반하는 상태가 된다
    (PostgreSQL에서 500. SQLite는 FK를 강제하지 않아 드러나지 않았다).

    여러 곳에서 각자 정규화하면 검사와 저장이 어긋나므로 이 함수 하나만 쓴다.
    """
    return raw.strip().lower()


def list_personas(db: Session) -> list[Persona]:
    return list(db.scalars(select(Persona).order_by(Persona.id)))


def list_scenarios(db: Session) -> list[Scenario]:
    return list(db.scalars(select(Scenario).order_by(Scenario.id)))


def find_persona(db: Session, persona_id: str) -> Persona | None:
    """id는 대소문자를 구분하지 않는다(클라이언트가 보내는 값을 관대하게 받는다)."""
    return db.scalar(select(Persona).where(Persona.id == canonical_id(persona_id)))


def find_scenario(db: Session, scenario_id: str) -> Scenario | None:
    return db.scalar(select(Scenario).where(Scenario.id == canonical_id(scenario_id)))


def is_paired(db: Session, persona_id: str, scenario_id: str) -> bool:
    """이 상대로 이 시나리오를 고를 수 있는가.

    관계를 통해 목록을 불러와 확인하지 않는다. 한 조합만 알면 되므로 그 행만 조회한다.
    """
    return (
        db.scalar(
            select(persona_scenarios.c.persona_id).where(
                persona_scenarios.c.persona_id == canonical_id(persona_id),
                persona_scenarios.c.scenario_id == canonical_id(scenario_id),
            )
        )
        is not None
    )
