"""채팅방·메시지·피드백 API의 요청/응답 DTO."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# CategoryScores/FeedbackIssue는 여기로 옮기지 않는다. 이 둘은 FeedbackResult의 일부로
# chat_feedbacks.result_json에 그대로 저장·역직렬화되는 **영속 계약**이라, 소유권이
# app/services/feedback.py에 있다. HTTP 응답인 FeedbackResponse만 여기 두고 임베드한다.
from app.services.feedback import CategoryScores, FeedbackIssue

# 카탈로그 id는 공백을 걷어낸 뒤 비면 안 된다.
#
# scenario_id에 이 제약이 없던 동안 ""와 "   "의 결과가 갈렸다. ""는 라우터의 진리값
# 분기(`if request.scenario_id:`)를 그냥 통과해 **자유 수다 방으로 조용히 강등**됐고(201),
# "   "는 카탈로그 조회에 실패해 400이 됐다. 둘 다 "시나리오를 고르려다 값이 빈" 요청이므로
# 같게 다뤄야 한다. 시나리오를 고르지 않겠다는 뜻은 **필드를 보내지 않거나 null**이다.
CatalogId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


class CreateRoomRequest(BaseModel):
    """방 주인은 요청 본문이 아니라 토큰에서 온다.

    `user_id`를 본문으로 받으면 아무나 남의 id를 적어 그 사람 이름으로 방을 만들 수 있다.
    """

    persona_id: CatalogId
    # None이면 시나리오 없는 자유 수다 방이다(무한정 대화. 턴 상한도 종료 조건도 없다).
    scenario_id: CatalogId | None = Field(default=None)
    # TODO(name): 지금은 클라이언트가 반드시 보내야 한다. personas.first_name을 써서
    #   "{이름} M/D HH:MM" 자동 생성으로 바꾸고 선택값으로 되돌릴 것.
    name: str = Field(min_length=1, max_length=200)


class RoomResponse(BaseModel):
    id: str
    user_id: str | None
    guest: bool
    persona_id: str
    scenario_id: str | None
    name: str
    created_at: datetime
    status: str
    turn_count: int


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
