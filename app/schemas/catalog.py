"""persona/scenario 카탈로그 조회 DTO."""

from pydantic import BaseModel


class PersonaItem(BaseModel):
    id: str
    description: str
    voice_id: str | None = None


class PersonaListResponse(BaseModel):
    personas: list[PersonaItem]


class ScenarioItem(BaseModel):
    id: str
    description: str


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioItem]
