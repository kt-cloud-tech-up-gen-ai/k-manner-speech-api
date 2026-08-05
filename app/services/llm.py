"""프롬프트 문자열 하나를 LLM에 던지고 텍스트를 돌려받는 공용 헬퍼."""

import logging

from fastapi import HTTPException, status

from app.core.config import CHAT_MODEL, get_api_key

logger = logging.getLogger(__name__)


def invoke_llm(prompt: str, temperature: float = 0.7) -> str:
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

    from app.routers.routers import extract_text_from_response

    return extract_text_from_response(response)
