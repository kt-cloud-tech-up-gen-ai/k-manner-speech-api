import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = next((p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents] 
             if(p / "data").exists()), Path(__file__).resolve().parents[3])
DATA = ROOT / "data"

load_dotenv(ROOT / ".env")
load_dotenv()

CHAT_MODEL = "gemini-2.5-flash"