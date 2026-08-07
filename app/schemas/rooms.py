"""채팅방·메시지·피드백 API의 요청/응답 DTO."""

from datetime import datetime

from pydantic import BaseModel, Field

# CategoryScores/FeedbackIssue는 여기로 옮기지 않는다. 이 둘은 FeedbackResult의 일부로
# chat_feedbacks.result_json에 그대로 저장·역직렬화되는 **영속 계약**이라, 소유권이
# app/services/feedback.py에 있다. HTTP 응답인 FeedbackResponse만 여기 두고 임베드한다.
from app.services.feedback import CategoryScores, FeedbackIssue


class CreateRoomRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    persona_id: str = Field(min_length=1, max_length=64)
    scenario_id: str | None = Field(default=None, max_length=64)
    # TODO(name): 지금은 클라이언트가 반드시 보내야 한다. persona/scenario YAML에 한글
    #   표시명이 추가되면 "{표시명} M/D HH:MM" 자동 생성으로 바꾸고 선택값으로 되돌릴 것.
    name: str = Field(min_length=1, max_length=200)


class RoomResponse(BaseModel):
    id: str
    user_id: str
    persona_id: str
    scenario_id: str | None
    name: str
    created_at: datetime


class RoomListResponse(BaseModel):
    rooms: list[RoomResponse]


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    question: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    answer: str
    message: ChatMessageResponse


class FeedbackResponse(BaseModel):
    score: int
    category_scores: CategoryScores
    summary: str
    strengths: list[str]
    improvements: list[str]
    issues: list[FeedbackIssue]
    cached: bool
