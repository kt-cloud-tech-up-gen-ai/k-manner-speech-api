from typing import Any

from app.prompt_builder.composer import PromptComposer


composer = PromptComposer("app/prompts")


def build_chat_prompt(question: str, persona: str | None = None, history: list[dict[str, Any]] | None = None) -> str:
    prompts = [
        *composer.load_bundle("base_chat"),
        *(composer.load_bundle(f"personas/{persona.strip().lower()}") if persona else []),
    ]
    base_prompt = composer.compose_by_priority(prompts)

    history_text = ""
    if history:
        history_lines = []
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                history_lines.append(f"- {role}: {content}")
        if history_lines:
            history_text = "\n\n대화 이력:\n" + "\n".join(history_lines)

    return f"{base_prompt}{history_text}\n\n사용자 질문: {question}"
