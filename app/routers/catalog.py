from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.catalog import (
    PersonaListResponse,
    PersonaResponse,
    PersonaSummaryResponse,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioSummaryResponse,
)
from app.services import catalog

router = APIRouter(tags=["catalog"])


@router.get("/personas", response_model=PersonaListResponse)
def list_personas(db: Session = Depends(get_db)) -> PersonaListResponse:
    """대화 상대 목록을 반환한다. 고르는 데 필요한 값만 담는다. (KAN-58)"""
    return PersonaListResponse(
        personas=[
            PersonaSummaryResponse.model_validate(persona, from_attributes=True)
            for persona in catalog.list_personas(db)
        ]
    )


@router.get("/personas/{persona_id}", response_model=PersonaResponse)
def get_persona(persona_id: str, db: Session = Depends(get_db)) -> PersonaResponse:
    """대화 상대 단건을 반환한다. 관계·음성 등 상세 값까지 포함한다."""
    persona = catalog.find_persona(db, persona_id)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"알 수 없는 persona입니다: {persona_id}",
        )
    return PersonaResponse.model_validate(persona, from_attributes=True)


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios(db: Session = Depends(get_db)) -> ScenarioListResponse:
    """대화 시나리오 목록을 반환한다. 어떤 상황인지 알아볼 값만 담는다. (KAN-59)"""
    return ScenarioListResponse(
        scenarios=[
            ScenarioSummaryResponse.model_validate(scenario, from_attributes=True)
            for scenario in catalog.list_scenarios(db)
        ]
    )


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: str, db: Session = Depends(get_db)) -> ScenarioResponse:
    """시나리오 단건을 반환한다. 목표·종료조건·턴 상한까지 포함한다."""
    scenario = catalog.find_scenario(db, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"알 수 없는 시나리오입니다: {scenario_id}",
        )
    return ScenarioResponse.model_validate(scenario, from_attributes=True)
