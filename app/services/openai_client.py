from functools import lru_cache
from typing import Any

from app.core.config import get_openai_api_key


class OpenAIConfigurationError(RuntimeError):
    """OpenAI SDK or API key is unavailable."""


@lru_cache(maxsize=1)
def get_openai_client() -> Any:
    api_key = get_openai_api_key()
    if not api_key:
        raise OpenAIConfigurationError("OPENAI_API_KEY가 설정되지 않았습니다.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIConfigurationError(
            "OpenAI SDK가 설치되지 않았습니다. requirements.txt를 설치해 주세요."
        ) from exc
    return OpenAI(api_key=api_key, timeout=30.0, max_retries=2)


def clear_openai_client_cache() -> None:
    get_openai_client.cache_clear()
