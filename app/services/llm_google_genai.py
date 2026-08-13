"""2026-08-11에 보존한 Google GenAI 직접 채팅 provider. 임시 파일임 안쓰는 파일

활성 provider는 ``app.services.llm``이다. 향후 LangChain에서 되돌릴 때
이 모듈의 provider 함수를 ``llm.py``에 재적용한다.
"""

import logging
from collections.abc import Mapping

from fastapi import HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import CHAT_MODEL, get_api_key
from app.prompt_builder.general_chat import build_chat_prompt

logger = logging.getLogger(__name__)


class ChatGeneration(BaseModel):
    answer: str = Field(min_length=1, description="사용자에게 보여줄 채팅 답변")
    response_style: str = Field(min_length=1, description="답변에 사용한 말투")


def get_chat_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


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
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="LLM API가 구성되지 않았습니다.")
    try:
        client = get_chat_client(api_key)
        response = client.models.generate_content(
            model=CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=ChatGeneration,
            ),
        )
        if response.parsed is None:
            raise RuntimeError("채팅 구조화 응답을 해석하지 못했습니다.")
        return ChatGeneration.model_validate(response.parsed)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="LLM 응답 시간이 초과되었습니다.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Structured Google GenAI request failed")
        raise HTTPException(status_code=502, detail="LLM 구조화 응답 호출에 실패했습니다.") from exc


def invoke_llm(prompt: str, temperature: float = 0.7) -> str:
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="LLM API가 구성되지 않았습니다.")
    try:
        client = get_chat_client(api_key)
        response = client.models.generate_content(
            model=CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
        )
        answer = response.text
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("채팅 응답에 텍스트가 없습니다.")
        return answer
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="LLM 응답 시간이 초과되었습니다.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Google GenAI request failed")
        raise HTTPException(status_code=502, detail="LLM 호출에 실패했습니다.") from exc
