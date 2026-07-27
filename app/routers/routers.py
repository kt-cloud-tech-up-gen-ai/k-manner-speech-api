import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import CHAT_MODEL
from app.prompts.chat.general_chat import build_chat_prompt


router = APIRouter()


class ChatRequest(BaseModel):
    question: str


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/chat")
def chat(request: ChatRequest):
    answer = generate_answer(request.question)
    return {"answer": answer}


def generate_answer(question: str) -> str:
    prompt = build_chat_prompt(question)

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage

            llm = ChatGoogleGenerativeAI(
                model=CHAT_MODEL,
                google_api_key=api_key,
                temperature=0.7,
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            content = getattr(response, "content", response)
            if isinstance(content, list):
                return "\n".join(str(item) for item in content)
            return str(content)
        except Exception as exc:
            return f"LLM 호출 중 오류가 발생했습니다: {exc}"

    return f"질문에 대한 답변을 준비했습니다. {question}"

