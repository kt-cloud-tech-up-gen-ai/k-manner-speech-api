import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

load_dotenv(ROOT / ".env")
load_dotenv()

# 모델 버전의 코드 기본값. .env에서 각 변수를 설정하면 그 값이 우선한다.
DEFAULT_CHAT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_EMOTION_MODEL = "gemini-3.1-flash-lite"

CHAT_MODEL = os.getenv("CHAT_MODEL", DEFAULT_CHAT_MODEL)
FEEDBACK_MODEL = os.getenv("FEEDBACK_MODEL", "gpt-5.6-luna")


@dataclass(frozen=True)
class Settings:
    """Gemini emotion-analysis settings."""

    gemini_api_key: str
    emotion_model: str


@lru_cache
def get_settings() -> Settings:
    """Return validated settings for the emotion-analysis endpoint."""

    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(".env 파일에 GOOGLE_API_KEY 또는 GEMINI_API_KEY를 입력하세요.")
    return Settings(
        gemini_api_key=api_key,
        emotion_model=os.getenv("EMOTION_MODEL", DEFAULT_EMOTION_MODEL),
    )


def get_api_key() -> str | None:
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def get_openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")
