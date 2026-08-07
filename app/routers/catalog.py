from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.catalog import (
    PersonaItem,
    PersonaListResponse,
    ScenarioItem,
    ScenarioListResponse,
)
from app.services import catalog

router = APIRouter(tags=["catalog"])


@router.get("/personas", response_model=PersonaListResponse)
def list_personas(db: Session = Depends(get_db)) -> PersonaListResponse:
    """대화 상대 persona 목록을 반환한다. (KAN-58)"""
    return PersonaListResponse(
        personas=[
            PersonaItem.model_validate(persona, from_attributes=True)
            for persona in catalog.list_personas(db)
        ]
    )


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios(db: Session = Depends(get_db)) -> ScenarioListResponse:
    """대화 시나리오(모드) 목록을 반환한다. (KAN-59)"""
    return ScenarioListResponse(
        scenarios=[
            ScenarioItem.model_validate(scenario, from_attributes=True)
            for scenario in catalog.list_scenarios(db)
        ]
    )
