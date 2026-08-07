"""persona/scenario 카탈로그 조회 DTO.

각 값이 무엇이고 클라이언트가 어떻게 쓰는지를 이 파일이 규정한다.
DB 컬럼(`app/models/catalog.py`)과 필드가 겹치지만 목적이 다르다.
컬럼은 저장 모양이고 여기는 API 계약이라, 노출하지 않을 값은 여기에 두지 않는다.

필수/선택은 DB의 NOT NULL과 일치시킨다. 선택값(`| None`)은 "아직 안 정해짐"이 아니라
"없어도 기능이 성립함"이라는 뜻이며, 각 필드 주석에 없을 때의 동작을 적는다.
"""

from pydantic import BaseModel, Field

from app.models.user import Gender


class PersonaItem(BaseModel):
    """대화 상대 1건. `POST /rooms`의 persona_id로 다시 들어온다."""

    id: str = Field(description="채팅방 생성 시 persona_id로 그대로 보내는 식별자")
    first_name: str = Field(description="이름. 화면 표시와 프롬프트 호칭에 쓰인다")
    middle_name: str | None = Field(
        default=None, description="없으면 이름 표기에서 생략한다"
    )
    last_name: str | None = Field(
        default=None, description="없으면 이름 표기에서 생략한다"
    )
    age: int = Field(description="만 나이. 사용자와의 나이 차가 존댓말/반말을 가른다")
    gender: Gender = Field(description="성별. 3인칭 표현과 음성 선택에 쓰인다")
    description: str = Field(description="목록 화면에 보여 주는 한 줄 소개")
    relationship_description: str = Field(
        description="사용자와의 관계. 호칭과 존대 수준을 정한다"
    )
    voice_id: str | None = Field(
        default=None,
        description="ElevenLabs 음성 id. 없으면 ELEVENLABS_VOICE_ID 기본 음성을 쓴다",
    )


class PersonaListResponse(BaseModel):
    personas: list[PersonaItem]


class ScenarioItem(BaseModel):
    """대화 시나리오 1건. `POST /rooms`의 scenario_id로 다시 들어온다."""

    id: str = Field(description="채팅방 생성 시 scenario_id로 그대로 보내는 식별자")
    description: str = Field(description="목록 화면에 보여 주는 한 줄 소개")
    time_context: str | None = Field(
        default=None, description="시간 배경. 없으면 프롬프트에서 시간을 언급하지 않는다"
    )
    place_context: str | None = Field(
        default=None, description="공간 배경. 없으면 프롬프트에서 장소를 언급하지 않는다"
    )
    communication_goal: str = Field(
        description="사용자가 달성해야 하는 의사소통 목표. 피드백 채점 기준이 된다"
    )
    end_condition: str = Field(description="대화를 끝내도 되는 조건")
    max_turns: int = Field(
        description="턴 상한. 종료 조건이 걸리지 않아도 이 턴 수에서 마무리한다"
    )


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioItem]
