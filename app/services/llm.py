"""LangChain을 거치는 일반 채팅 LLM 호출.

프롬프트 조합(app/prompt_builder/)을 적용해야 하는 경로를 담당한다.
systemInstruction/generationConfig를 원본 그대로 넘기는 경로는 services/gemini.py.
"""

import logging
from typing import Any

from fastapi import HTTPException, status

from app.core.config import CHAT_MODEL, get_api_key
from app.prompt_builder.general_chat import build_chat_prompt

logger = logging.getLogger(__name__)


def generate_answer(question: str, persona: str) -> str:
    """질문과 persona로 프롬프트를 조합해 LLM 답변을 받는다."""
    return invoke_llm(build_chat_prompt(question, persona=persona))


def invoke_llm(prompt: str, temperature: float = 0.7) -> str:
    """프롬프트 문자열 하나를 LLM에 던지고 텍스트를 돌려받는다."""
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM API가 구성되지 않았습니다.",
        )

    try:
        from langchain_core.messages import HumanMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=CHAT_MODEL,
            google_api_key=api_key,
            temperature=temperature,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
    except TimeoutError as exc:
        logger.exception("LLM request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM 응답 시간이 초과되었습니다.",
        ) from exc
    except Exception as exc:
        logger.exception("LLM request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM 호출에 실패했습니다.",
        ) from exc

    return extract_text_from_response(response)


def extract_text_from_response(response: Any) -> str:
    """LangChain 응답 객체에서 텍스트만 재귀적으로 뽑아낸다.

    모델·버전에 따라 content가 str / list[str|dict] / dict로 오므로 전부 받아낸다.
    """
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
        return "".join(part for part in parts if part)

    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        if isinstance(text, str):
            return text

    return str(content)
