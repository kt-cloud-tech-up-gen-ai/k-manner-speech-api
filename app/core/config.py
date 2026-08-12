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


# 웹 프론트가 :5173, API가 :8000 이라 출처가 다르다. 미설정 시 로컬 개발 출처만 허용한다.
# localhost와 127.0.0.1은 브라우저에게 서로 다른 출처라 둘 다 넣는다.
DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def get_cors_allow_origins() -> list[str]:
    """CORS_ALLOW_ORIGINS(쉼표 구분)를 파싱한다. 값이 없거나 비면 기본값."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    # "".split(",") == [""] — 빈 항목을 그대로 두면 아무 출처와도 매칭되지 않는 항목이 남는다.
    # 끝의 슬래시도 제거한다(브라우저는 Origin 헤더를 슬래시 없이 보낸다).
    origins = [o.strip().rstrip("/") for o in raw.split(",")]
    origins = [o for o in origins if o]
    return origins or list(DEFAULT_CORS_ALLOW_ORIGINS)
