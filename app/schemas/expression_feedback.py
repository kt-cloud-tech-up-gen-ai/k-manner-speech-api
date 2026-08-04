from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Relationship(str, Enum):
    COWORKER = "coworker"
    CUSTOMER = "customer"
    FRIEND = "friend"
    FAMILY = "family"
    TEACHER_STUDENT = "teacher_student"
    OTHER = "other"


class RelativeStatus(str, Enum):
    SENIOR = "senior"
    PEER = "peer"
    JUNIOR = "junior"
    UNKNOWN = "unknown"


class Formality(str, Enum):
    FORMAL = "formal"
    POLITE = "polite"
    CASUAL = "casual"


class CommunicationType(str, Enum):
    SPOKEN = "spoken"
    WRITTEN = "written"


class PreviousUtterance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["speaker", "listener"] = Field(
        description="발화자 역할. 평가 대상 화자는 speaker, 상대방은 listener",
    )
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ExpressionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_utterances: list[PreviousUtterance] = Field(
        default_factory=list,
        max_length=10,
        description="시간순으로 정렬한 최근 대화",
    )
    situation: str | None = Field(default=None, max_length=500)
    relationship: Relationship | None = None
    relative_status: RelativeStatus | None = None
    formality: Formality | None = None
    communication_type: CommunicationType | None = None


class ExpressionFeedbackRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "text": "저는 지난주에 고객 미팅을 진행해요.",
                    "context": {
                        "previous_utterances": [
                            {
                                "speaker": "listener",
                                "text": "지난주에는 어떤 업무를 했어요?",
                            }
                        ],
                        "situation": "지난주 업무 보고",
                        "relationship": "coworker",
                        "relative_status": "peer",
                        "formality": "polite",
                        "communication_type": "spoken",
                    },
                }
            ]
        },
    )

    text: str = Field(
        min_length=1,
        max_length=1000,
        description="표현 피드백을 받을 문장",
    )
    context: ExpressionContext | None = None

    @field_validator("text", mode="before")
    @classmethod
    def strip_and_validate_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("text는 공백일 수 없습니다.")
        return value


class ExpressionIssueType(str, Enum):
    TENSE = "tense"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    NATURALNESS = "naturalness"
    HONORIFIC = "honorific"
    POLITENESS = "politeness"
    CONTEXT = "context"
    OTHER = "other"


class ExpressionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ExpressionIssueType
    expression: str = Field(description="원문에서 개선이 필요한 표현")
    suggestion: str = Field(description="대체할 표현")
    reason: str = Field(description="개선이 필요한 이유")


class ExpressionFeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str = Field(description="문맥을 반영한 전체 표현 피드백")
    suggested_text: str = Field(description="추천하는 전체 문장")
    issues: list[ExpressionIssue] = Field(
        description="발견된 표현 문제. 문제가 없으면 빈 배열",
    )
