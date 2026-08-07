import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

load_dotenv(ROOT / ".env")
load_dotenv()

CHAT_MODEL = "gemini-2.5-flash"
FEEDBACK_MODEL = os.getenv("FEEDBACK_MODEL", "gpt-5.6-luna")


def get_api_key() -> str | None:
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def get_openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")
