from pathlib import Path

from app.prompts.composer import PromptComposer


composer = PromptComposer(Path(__file__).resolve().parent)


def build_expression_feedback_instructions() -> str:
    return composer.compose_by_name(tasks=["expression_feedback"])
