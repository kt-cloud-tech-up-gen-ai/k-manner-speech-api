from app.prompts.composer import PromptComposer


composer = PromptComposer("app/prompts")


def build_chat_prompt(question: str) -> str:
    prompts = [
        composer.load("identities", "friend"),
        composer.load("personalities", "friendly"),
        composer.load("rules", "safety"),
        composer.load("rules", "no_hallucination"),
        composer.load("styles", "concise"),
    ]
    base_prompt = composer.compose_by_priority(prompts)
    return f"{base_prompt}\n\n사용자 질문: {question}"