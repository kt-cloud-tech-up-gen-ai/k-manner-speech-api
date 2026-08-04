import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")
load_dotenv()

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.5-flash")

EXPRESSION_FEEDBACK_MODEL = os.getenv(
    "OPENAI_EXPRESSION_FEEDBACK_MODEL",
    "gpt-5.6-terra",
)
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
