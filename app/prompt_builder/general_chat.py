from app.prompt_builder.composer import PromptComposer


composer = PromptComposer("app/prompts")

# 프롬프트에 표시할 화자 이름. 여기 없는 role은 이력에서 제외한다.
SPEAKER_LABELS = {"user": "사용자", "assistant": "상대"}


def build_chat_prompt(
    question: str,
    persona: str | None = None,
    history: list[dict[str, str]] | None = None,
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
