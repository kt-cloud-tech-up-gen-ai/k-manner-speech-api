"""환경에 설정된 모델에 맞춰 OpenAI 또는 Gemini로 채팅을 생성한다."""

import logging
import os
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.config import CHAT_MODEL, get_api_key
from app.prompt_builder.general_chat import build_chat_prompt
from app.services.openai_client import OpenAIConfigurationError, get_openai_client

logger = logging.getLogger(__name__)


class ChatGeneration(BaseModel):
    answer: str = Field(min_length=1, description="사용자에게 보여줄 채팅 답변")
    response_style: str = Field(min_length=1, description="답변에 사용한 말투")


def get_chat_model(api_key: str, temperature: float = 0.7) -> Any:
    """테스트에서 provider 경계를 대체할 수 있게 LangChain 모델을 생성한다."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        google_api_key=api_key,
        temperature=temperature,
    )


def _uses_openai() -> bool:
    return CHAT_MODEL.startswith(("gpt-", "o1", "o3", "o4"))


def _openai_reasoning() -> dict[str, str]:
    return {"effort": os.getenv("CHAT_REASONING_EFFORT", "low")}


def _is_timeout(exc: Exception) -> bool:
    return isinstance(exc, TimeoutError) or type(exc).__name__ == "APITimeoutError"


def generate_answer(
    question: str,
    persona: str,
    history: list[dict[str, str]] | None = None,
    scenario: Mapping[str, object] | None = None,
) -> str:
    return invoke_llm(
        build_chat_prompt(
            question,
            persona=persona,
            history=history,
            scenario=scenario,
        )
    )


def generate_structured_answer(
    question: str,
    persona: str,
    analysis: dict[str, str],
    history: list[dict[str, str]] | None = None,
    scenario: Mapping[str, object] | None = None,
) -> ChatGeneration:
    prompt = build_chat_prompt(
        question,
        persona=persona,
        history=history,
        analysis=analysis,
        scenario=scenario,
    )
    return invoke_structured_llm(prompt)


def invoke_structured_llm(prompt: str, temperature: float = 0.7) -> ChatGeneration:
    if _uses_openai():
        try:
            response = get_openai_client().responses.parse(
                model=CHAT_MODEL,
                reasoning=_openai_reasoning(),
                input=prompt,
                text_format=ChatGeneration,
                store=False,
            )
            if response.output_parsed is None:
                raise RuntimeError("채팅 구조화 응답을 해석하지 못했습니다.")
            return ChatGeneration.model_validate(response.output_parsed)
        except OpenAIConfigurationError as exc:
            raise HTTPException(status_code=503, detail="LLM API가 구성되지 않았습니다.") from exc
        except Exception as exc:
            if _is_timeout(exc):
                logger.exception("Structured OpenAI chat request timed out")
                raise HTTPException(
                    status_code=504, detail="LLM 응답 시간이 초과되었습니다."
                ) from exc
            logger.exception("Structured OpenAI chat request failed")
            raise HTTPException(
                status_code=502, detail="LLM 구조화 응답 호출에 실패했습니다."
            ) from exc

    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="LLM API가 구성되지 않았습니다.")
    try:
        from langchain_core.messages import HumanMessage

        structured_model = get_chat_model(api_key, temperature).with_structured_output(
            ChatGeneration
        )
        response = structured_model.invoke([HumanMessage(content=prompt)])
        return ChatGeneration.model_validate(response)
    except TimeoutError as exc:
        logger.exception("Structured LLM request timed out")
        raise HTTPException(status_code=504, detail="LLM 응답 시간이 초과되었습니다.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Structured LLM request failed")
        raise HTTPException(status_code=502, detail="LLM 구조화 응답 호출에 실패했습니다.") from exc


def invoke_llm(prompt: str, temperature: float = 0.7) -> str:
    if _uses_openai():
        try:
            response = get_openai_client().responses.create(
                model=CHAT_MODEL,
                reasoning=_openai_reasoning(),
                input=prompt,
                store=False,
            )
            answer = response.output_text
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("채팅 응답에 텍스트가 없습니다.")
            return answer
        except OpenAIConfigurationError as exc:
            raise HTTPException(status_code=503, detail="LLM API가 구성되지 않았습니다.") from exc
        except Exception as exc:
            if _is_timeout(exc):
                logger.exception("OpenAI chat request timed out")
                raise HTTPException(
                    status_code=504, detail="LLM 응답 시간이 초과되었습니다."
                ) from exc
            logger.exception("OpenAI chat request failed")
            raise HTTPException(status_code=502, detail="LLM 호출에 실패했습니다.") from exc

    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="LLM API가 구성되지 않았습니다.")
    try:
        from langchain_core.messages import HumanMessage

        response = get_chat_model(api_key, temperature).invoke([HumanMessage(content=prompt)])
        answer = extract_text_from_response(response)
        if not answer.strip():
            raise RuntimeError("채팅 응답에 텍스트가 없습니다.")
        return answer
    except TimeoutError as exc:
        logger.exception("LLM request timed out")
        raise HTTPException(status_code=504, detail="LLM 응답 시간이 초과되었습니다.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("LLM request failed")
        raise HTTPException(status_code=502, detail="LLM 호출에 실패했습니다.") from exc


def extract_text_from_response(response: Any) -> str:
    if response is None:
        return ""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
            else:
                parts.append(extract_text_from_response(item))
        return "".join(parts)
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        if isinstance(text, str):
            return text
    return str(content)
