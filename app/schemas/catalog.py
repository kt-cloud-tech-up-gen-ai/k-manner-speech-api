"""persona/scenario 카탈로그 조회 DTO."""

from pydantic import BaseModel


class PersonaResponse(BaseModel):
    id: str
    description: str
    voice_id: str | None = None


class PersonaListResponse(BaseModel):
    personas: list[PersonaResponse]


class ScenarioResponse(BaseModel):
    id: str
    description: str


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioResponse]
