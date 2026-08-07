"""persona / 시나리오 카탈로그 조회.

출처는 DB(`personas`, `scenarios`)다. 예전에는 프롬프트 YAML을 스캔해 목록을 만들었지만,
같은 값이 파일과 DB 두 곳에 존재하면 어느 쪽이 맞는지 알 수 없어 DB 하나로 모았다.

캐시는 두지 않는다. 카탈로그는 요청당 한 번 읽는 작은 테이블이고, 캐시를 두면
관리 API로 값을 고쳤을 때 프로세스마다 다른 값을 보게 된다.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Persona, Scenario


def list_personas(db: Session) -> list[Persona]:
    return list(db.scalars(select(Persona).order_by(Persona.id)))


def list_scenarios(db: Session) -> list[Scenario]:
    return list(db.scalars(select(Scenario).order_by(Scenario.id)))


def find_persona(db: Session, persona_id: str) -> Persona | None:
    """id는 대소문자를 구분하지 않는다(클라이언트가 보내는 값을 관대하게 받는다)."""
    return db.scalar(select(Persona).where(Persona.id == persona_id.strip().lower()))


def find_scenario(db: Session, scenario_id: str) -> Scenario | None:
    return db.scalar(select(Scenario).where(Scenario.id == scenario_id.strip().lower()))
