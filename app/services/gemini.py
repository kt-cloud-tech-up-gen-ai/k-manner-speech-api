"""Gemini generateContent REST API 직접 호출.

LangChain을 거치지 않고 systemInstruction·generationConfig를 그대로 전달해야 하는
`/ask_gemini` 전용 경로다. 프롬프트 조합을 거치는 일반 채팅은 services/llm.py를 쓴다.

의존성 추가 없이 표준 라이브러리(urllib)로 호출한다(app/core/auth.py의 Supabase 호출과 같은 방식).
"""

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import HTTPException, status

from app.core.config import CHAT_MODEL, get_api_key

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60


def generate_content(
    system_instruction: str,
    contents: str,
    generation_config: dict[str, Any] | None = None,
) -> str:
    """Gemini에 시스템 지침·입력 텍스트·생성 설정을 보내고 답변 텍스트를 돌려준다.

    실패는 모두 HTTPException으로 변환한다. upstream이 4xx면 요청이 잘못된 것이므로
    400으로, 5xx·타임아웃·연결 실패는 우리 쪽에서 손쓸 수 없으므로 502/504로 매핑한다.
    """
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API가 구성되지 않았습니다.",
        )

    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": contents}]}],
    }
    if generation_config:
        payload["generationConfig"] = generation_config

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
        with urlopen(api_request, timeout=TIMEOUT_SECONDS) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        return extract_gemini_answer(response_data)
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
