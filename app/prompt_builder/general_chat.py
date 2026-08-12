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
) -> str:
    """시스템 프롬프트 + (선택) 대화 이력 + 이번 질문을 하나의 프롬프트로 합친다.

    history는 `{"role": "user"|"assistant", "content": ...}` 목록이며 오래된 순이다.
    잘라내기는 호출자 책임이다(routers/rooms.py의 HISTORY_LIMIT).
    """
    prompts = [
        *composer.load_bundle("base_chat"),
        *(composer.load_bundle(f"personas/{persona.strip().lower()}") if persona else []),
    ]
    base_prompt = composer.compose_by_priority(prompts)

    sections = [base_prompt]
    transcript = _format_history(history)
    if transcript:
        sections.append(f"## 대화 이력\n{transcript}")
    if analysis:
        sections.append(_format_analysis(question, analysis))
    sections.append(f"사용자 질문: {question}")

    return "\n\n".join(sections)


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
