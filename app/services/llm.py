"""LangChain Google Gemini provider를 사용하는 채팅 서비스."""

import logging
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.config import CHAT_MODEL, get_api_key
from app.prompt_builder.general_chat import build_chat_prompt

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


def generate_answer(
    question: str,
    persona: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    return invoke_llm(build_chat_prompt(question, persona=persona, history=history))


def generate_structured_answer(
    question: str,
    persona: str,
    analysis: dict[str, str],
    history: list[dict[str, str]] | None = None,
) -> ChatGeneration:
    prompt = build_chat_prompt(question, persona=persona, history=history, analysis=analysis)
    return invoke_structured_llm(prompt)


def invoke_structured_llm(prompt: str, temperature: float = 0.7) -> ChatGeneration:
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
