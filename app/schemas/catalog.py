"""persona/scenario 카탈로그 조회 DTO.

각 값이 무엇이고 클라이언트가 어떻게 쓰는지를 이 파일이 규정한다.
DB 컬럼(`app/models/catalog.py`)과 필드가 겹치지만 목적이 다르다.
컬럼은 저장 모양이고 여기는 API 계약이라, 노출하지 않을 값은 여기에 두지 않는다.

## 요약 응답과 단건 응답을 나누는 기준

- `...SummaryResponse`: **고르기 위한 정보**. 목록 화면이 카드를 그리는 데 필요한 값만.
- `...Response`: **고른 뒤에 필요한 정보**. 요약을 포함하고 상세 값을 더한다.

둘을 나눈 이유는 분량이 아니라 사용 시점이다. 제목·난이도·예상 시간과
`communication_goal`은 목록 카드가 직접 표시하므로 요약에도 포함한다.
`end_condition`·`max_turns`는 대화를 시작한 뒤에만 필요하므로 단건 조회로 미룬다.

`relationship_description`도 같은 이유로 단건에 둔다. 화면에 쓸 수는 있지만 본래 목적은
프롬프트의 호칭·존대 수준 결정이다.

`scenarios.turn_limit_exit_line`은 어느 DTO에도 넣지 않는다. 턴 상한에서 persona가 할 말은
대화 메시지로 전달되므로 카탈로그 응답으로 미리 내려 줄 이유가 없다.

## 상세 응답의 상호 임베드

persona 상세에는 고를 수 있는 시나리오 목록이, 시나리오 상세에는 그 상황을 연습할 수 있는
상대 목록이 실린다. 양쪽 모두 **요약 DTO**를 담는다. 상세를 담으면 서로를 무한히 참조한다.

## 정의 순서

요약 DTO 둘을 파일 맨 위에 둔다. 상세 DTO가 반대쪽 요약을 필드 타입으로 쓰기 때문에,
순서가 뒤바뀌면 임포트 시점에 이름을 찾지 못한다.

## 필수/선택

DB의 NOT NULL과 일치시킨다. 선택값(`| None`)은 "아직 안 정해짐"이 아니라
"없어도 기능이 성립함"이라는 뜻이며, 각 필드 주석에 없을 때의 동작을 적는다.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import Gender


class PersonaSummaryResponse(BaseModel):
    """대화 상대 목록의 원소. 상대를 고르는 데 필요한 값만 담는다."""

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


class ScenarioSummaryResponse(BaseModel):
    """시나리오 목록의 원소. 어떤 상황인지 알아보는 데 필요한 값만 담는다."""

    id: str = Field(description="채팅방 생성 시 scenario_id로 그대로 보내는 식별자")
    title_ko: str = Field(description="목록 카드에 표시하는 한국어 제목")
    title_en: str | None = Field(
        default=None, description="목록 카드에 표시하는 영어 제목. 없으면 생략한다"
    )
    description: str = Field(description="목록 화면에 보여 주는 한 줄 소개")
    communication_goal: str = Field(description="목록 카드에 표시하는 대화 연습 목표")
    time_context: str | None = Field(
        default=None, description="시간 배경. 없으면 시간을 표시하지 않는다"
    )
    place_context: str | None = Field(
        default=None, description="공간 배경. 없으면 장소를 표시하지 않는다"
    )
    difficulty: str | None = Field(
        default=None, description="화면에 표시할 난이도. 없으면 easy로 표시한다"
    )
    estimated_minutes: int | None = Field(
        default=None, description="예상 연습 시간(분). 없으면 턴 수로 추정한다"
    )
    is_featured: bool = Field(description="추천 시나리오 표시 여부")


class PersonaResponse(PersonaSummaryResponse):
    """대화 상대 단건. 대화를 시작한 뒤에 필요한 값까지 포함한다."""

    relationship_description: str = Field(
        description="사용자와의 관계. 호칭과 존대 수준을 정한다"
    )
    version: datetime = Field(
        description="정의가 마지막으로 바뀐 시각. 클라이언트 캐시 무효화에 쓴다"
    )
    scenarios: list[ScenarioSummaryResponse] = Field(
        description=(
            "이 상대로 고를 수 있는 시나리오. id 오름차순. 빈 배열이면 아직 준비된 상황이"
            " 없다는 뜻이다. 여기 없는 조합으로 채팅방을 만들면 400이다"
        )
    )


class PersonaListResponse(BaseModel):
    personas: list[PersonaSummaryResponse]


class ScenarioResponse(ScenarioSummaryResponse):
    """시나리오 단건. 대화 진행 규칙까지 포함한다."""

    end_condition: str = Field(description="대화를 끝내도 되는 조건")
    max_turns: int = Field(
        description="턴 상한. 종료 조건이 걸리지 않아도 이 턴 수에서 마무리한다"
    )
    version: datetime = Field(
        description="정의가 마지막으로 바뀐 시각. 클라이언트 캐시 무효화에 쓴다"
    )
    personas: list[PersonaSummaryResponse] = Field(
        description="이 상황을 연습할 수 있는 상대. id 오름차순"
    )


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioSummaryResponse]
