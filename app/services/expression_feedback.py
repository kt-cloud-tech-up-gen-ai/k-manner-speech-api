import logging
import os

from openai import AsyncOpenAI, OpenAIError

from app.core.config import EXPRESSION_FEEDBACK_MODEL, OPENAI_TIMEOUT_SECONDS
from app.prompts.expression_feedback import build_expression_feedback_instructions
from app.schemas.expression_feedback import (
    ExpressionFeedbackRequest,
    ExpressionFeedbackResponse,
)


logger = logging.getLogger(__name__)


class ExpressionFeedbackConfigurationError(RuntimeError):
    """Raised when expression feedback is not configured."""


class ExpressionFeedbackGenerationError(RuntimeError):
    """Raised when the model cannot generate expression feedback."""


async def generate_expression_feedback(
    request: ExpressionFeedbackRequest,
    client: AsyncOpenAI | None = None,
) -> ExpressionFeedbackResponse:
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ExpressionFeedbackConfigurationError(
                "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
            )
        client = AsyncOpenAI(
            api_key=api_key,
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=2,
        )

    try:
        response = await client.responses.parse(
            model=EXPRESSION_FEEDBACK_MODEL,
            instructions=build_expression_feedback_instructions(),
            input=request.model_dump_json(exclude_none=True),
            text_format=ExpressionFeedbackResponse,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            max_output_tokens=600,
            store=False,
        )
    except OpenAIError as exc:
        logger.exception("OpenAI expression feedback request failed")
        raise ExpressionFeedbackGenerationError(
            "표현 피드백을 생성하지 못했습니다."
        ) from exc

    feedback = response.output_parsed
    if feedback is None:
        raise ExpressionFeedbackGenerationError(
            "모델이 구조화된 표현 피드백을 반환하지 않았습니다."
        )

    return feedback
