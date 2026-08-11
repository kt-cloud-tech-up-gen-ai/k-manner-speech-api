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


@dataclass(frozen=True)
class TtsSettings:
    """Gemini TTS 인증, 모델, 음성 및 출력 파일 설정."""

    google_api_key: str
    tts_model: str
    voice_name: str
    output_dir: Path


@lru_cache
def get_tts_settings() -> TtsSettings:
    """검증된 Gemini TTS 설정을 프로세스당 한 번 반환합니다."""

    api_key = (get_api_key() or "").strip()
    if not api_key:
        raise RuntimeError(".env 파일에 GOOGLE_API_KEY 또는 GEMINI_API_KEY를 입력하세요.")
    return TtsSettings(
        google_api_key=api_key,
        tts_model=os.getenv("TTS_MODEL", "gemini-3.1-flash-tts-preview"),
        voice_name=os.getenv("GEMINI_TTS_VOICE_NAME", "Kore"),
        output_dir=Path(os.getenv("TTS_OUTPUT_DIR", "app/outputs")),
    )
