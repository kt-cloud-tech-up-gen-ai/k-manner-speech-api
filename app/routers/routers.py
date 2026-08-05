import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import CHAT_MODEL, get_api_key
from app.prompt_builder.general_chat import build_chat_prompt


router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    persona: str
    history: list[dict[str, str]]
    question: str


class ChatResponse(BaseModel):
    answer: str


class GenerationConfig(BaseModel):
    """Gemini generateContent의 생성 설정."""

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    topP: float | None = Field(default=None, ge=0.0, le=1.0)
    topK: int | None = Field(default=None, ge=1)
    maxOutputTokens: int | None = Field(default=None, ge=1)
    candidateCount: int | None = Field(default=None, ge=1)
    stopSequences: list[str] | None = None
    responseMimeType: str | None = None


class AskGeminiRequest(BaseModel):
    systemInstruction: str
    contents: str
    generationConfig: GenerationConfig | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "systemInstruction": "당신의 이름은 도윤이고, 대학선배입니다. 한국어로 친절하게 답변하세요.",
                "contents": "선배님 안녕하세요",
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 1000,
                },
            }
        }
    }


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """사용자 질문, 페르소나, 대화 이력을 LLM에 전달한다."""
    if not request.question.strip():
        return ChatResponse(answer="질문을 입력해 주세요.")

    answer = generate_answer(
        request.question,
        persona=request.persona,
        history=request.history,
    )
    return ChatResponse(answer=answer)


@router.post("/ask_gemini", response_model=ChatResponse)
def ask_gemini(request: AskGeminiRequest) -> ChatResponse:
    """Gemini REST API에 시스템 지침, 입력 텍스트, 생성 설정을 전달한다."""
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API가 구성되지 않았습니다.",
        )

    payload = {
        "systemInstruction": {"parts": [{"text": request.systemInstruction}]},
        "contents": [{"role": "user", "parts": [{"text": request.contents}]}],
    }
    if request.generationConfig is not None:
        payload["generationConfig"] = request.generationConfig.model_dump(exclude_none=True)
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(CHAT_MODEL, safe='')}:generateContent"
    )
    api_request = UrlRequest(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(api_request, timeout=60) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        answer = extract_gemini_answer(response_data)
        return ChatResponse(answer=answer or "Gemini 응답에 텍스트가 없습니다.")
    except HTTPError as exc:
        upstream_body = _read_http_error_body(exc)
        logger.warning(
            "Gemini API returned HTTP %s: %s",
            exc.code,
            upstream_body or "<empty response body>",
        )
        client_status = 400 if 400 <= exc.code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail=f"Gemini API 요청이 거부되었습니다. (upstream HTTP {exc.code})",
        ) from exc
    except TimeoutError as exc:
        logger.exception("Gemini API request timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gemini API 응답 시간이 초과되었습니다.",
        ) from exc
    except URLError as exc:
        logger.exception("Could not connect to Gemini API")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini API에 연결하지 못했습니다.",
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
        logger.exception("Could not process Gemini API response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini API 응답을 처리하지 못했습니다.",
        ) from exc


def _read_http_error_body(exc: HTTPError) -> str:
    """진단용 upstream 본문을 읽되 로그가 과도하게 커지지 않게 제한한다."""
    try:
        return exc.read().decode("utf-8", errors="replace")[:4096]
    except OSError:
        return "<failed to read response body>"


def extract_gemini_answer(response_data: Any) -> str:
    """Gemini generateContent 응답의 모든 텍스트 파트를 결합한다."""
    if not isinstance(response_data, dict):
        return ""

    candidates = response_data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""

    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return ""

    return "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    )


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
        return "".join(part for part in parts if part)

    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        if isinstance(text, str):
            return text

    return str(content)


def generate_answer(question: str, persona: str, history: list[dict[str, str]]) -> str:
    prompt = build_chat_prompt(question, persona=persona, history=history)

    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM API가 구성되지 않았습니다.",
        )

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        llm = ChatGoogleGenerativeAI(
            model=CHAT_MODEL,
            google_api_key=api_key,
            temperature=0.7,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return extract_text_from_response(response)
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
