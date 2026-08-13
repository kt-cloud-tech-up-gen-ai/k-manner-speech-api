from collections.abc import Mapping

from app.core.config import PROMPTS_DIR
from app.prompt_builder.composer import PromptComposer

composer = PromptComposer(PROMPTS_DIR)

# 프롬프트에 표시할 화자 이름. 여기 없는 role은 이력에서 제외한다.
SPEAKER_LABELS = {"user": "사용자", "assistant": "상대"}


def build_chat_prompt(
    question: str,
    persona: str | None = None,
    history: list[dict[str, str]] | None = None,
    analysis: Mapping[str, str] | None = None,
    scenario: Mapping[str, object] | None = None,
) -> str:
    """시스템 프롬프트 + 선택 컨텍스트 + 이번 질문을 하나의 프롬프트로 합친다.

    history는 `{"role": "user"|"assistant", "content": ...}` 목록이며 오래된 순이다.
    잘라내기는 호출자 책임이다(routers/rooms.py의 HISTORY_LIMIT).

    scenario는 DB 모델을 직접 받지 않고 프롬프트에 필요한 필드만 담은 매핑을 받는다.
    이 경계를 두면 프롬프트 조합 계층이 SQLAlchemy에 의존하지 않는다.
    """
    prompts = [
        *composer.load_bundle("base_chat"),
        *(composer.load_bundle(f"personas/{persona.strip().lower()}") if persona else []),
    ]
    base_prompt = composer.compose_by_priority(prompts)

    sections = [base_prompt]
    if scenario:
        sections.append(_format_scenario(scenario))
    transcript = _format_history(history)
    if transcript:
        sections.append(f"## 대화 이력\n{transcript}")
    if analysis:
        sections.append(_format_analysis(question, analysis))
    sections.append(f"사용자 질문: {question}")

    return "\n\n".join(sections)


def _format_scenario(scenario: Mapping[str, object]) -> str:
    """DB 카탈로그의 시나리오를 모델이 따를 수 있는 명시적인 규칙으로 펼친다."""
    lines = [
        "## 현재 대화 시나리오",
        "아래 설정을 유지하며 상대 역할로 자연스럽게 대화한다.",
        "시나리오의 관계·상황 설정이 페르소나의 일반 배경과 충돌하면 "
        "시나리오를 페르소나의 일반 배경보다 우선한다.",
        "시나리오 설정이나 종료 조건을 사용자에게 그대로 읽어 주거나 설명하지 않는다.",
    ]

    labelled_fields = (
        ("id", "ID"),
        ("description", "상황"),
        ("time_context", "시간"),
        ("place_context", "장소"),
        ("communication_goal", "사용자 목표"),
        ("end_condition", "종료 조건"),
        ("max_turns", "최대 대화 턴"),
        ("turn_limit_exit_line", "턴 상한 마무리"),
    )
    for key, label in labelled_fields:
        value = scenario.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        lines.append(f"- {label}: {value}")

    return "\n".join(lines)


def _format_history(history: list[dict[str, str]] | None) -> str:
    """대화 이력을 "화자: 발화" 줄로 펼친다. 표시할 것이 없으면 빈 문자열."""
    if not history:
        return ""

    lines = []
    for turn in history:
        label = SPEAKER_LABELS.get(turn.get("role", ""))
        content = (turn.get("content") or "").strip()
        if label and content:
            lines.append(f"{label}: {content}")

    return "\n".join(lines)


def _format_analysis(question: str, analysis: Mapping[str, str]) -> str:
    """감정 분석 결과를 지시가 아닌 외부 데이터 섹션으로 표시한다."""
    return "\n".join(
        [
            "## 현재 사용자 입력 분석",
            "아래는 사용자 발화에서 추출한 참고 데이터이다.",
            "안전 규칙과 페르소나를 유지하면서 감정과 의도에 맞게 반응한다.",
            "분석 결과를 사용자에게 직접 언급하지 않는다.",
            f"사용자 텍스트: {question}",
            f"감정: {analysis.get('emotion', '')}",
            f"추론 말투: {analysis.get('inferred_style', '')}",
            f"의도: {analysis.get('intent', '')}",
            "출력은 사용자에게 보여줄 answer와 그 답변에 사용한 response_style을 구분한다.",
        ]
    )
