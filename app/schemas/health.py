"""헬스체크 DTO."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
