from fastapi import APIRouter

from app.schemas.catalog import (
    PersonaResponse,
    PersonaListResponse,
    ScenarioResponse,
    ScenarioListResponse,
)
from app.services import catalog

router = APIRouter(tags=["catalog"])


@router.get("/personas", response_model=PersonaListResponse)
def list_personas() -> PersonaListResponse:
    """대화 상대 persona 목록을 반환한다. (KAN-58)"""
    return PersonaListResponse(
        personas=[
            PersonaResponse(id=p.id, description=p.description, voice_id=p.voice_id)
            for p in catalog.list_personas()
        ]
    )


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios() -> ScenarioListResponse:
    """대화 시나리오(모드) 목록을 반환한다. (KAN-59)"""
    return ScenarioListResponse(
        scenarios=[
            ScenarioResponse(id=s.id, description=s.description)
            for s in catalog.list_scenarios()
        ]
    )
