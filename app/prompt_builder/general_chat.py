from app.prompt_builder.composer import PromptComposer


composer = PromptComposer("app/prompts")


def build_chat_prompt(question: str, persona: str | None = None) -> str:
    prompts = [
        *composer.load_bundle("base_chat"),
        *(composer.load_bundle(f"personas/{persona.strip().lower()}") if persona else []),
    ]
    base_prompt = composer.compose_by_priority(prompts)

    return f"{base_prompt}\n\n사용자 질문: {question}"
