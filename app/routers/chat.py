"""무상태 채팅 엔드포인트.

대화 이력을 저장하는 채팅은 routers/rooms.py에 있다.
"""

from fastapi import APIRouter

from app.schemas.chat import AskGeminiRequest, ChatRequest, ChatResponse
from app.services import gemini, llm

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """사용자 질문과 페르소나를 LLM에 전달한다."""
    if not request.question.strip():
        return ChatResponse(answer="질문을 입력해 주세요.")

    answer = llm.generate_answer(request.question, persona=request.persona)
    return ChatResponse(answer=answer)


@router.post("/ask_gemini", response_model=ChatResponse)
def ask_gemini(request: AskGeminiRequest) -> ChatResponse:
    """Gemini REST API에 시스템 지침, 입력 텍스트, 생성 설정을 전달한다."""
    generation_config = (
        request.generationConfig.model_dump(exclude_none=True)
        if request.generationConfig is not None
        else None
    )
    answer = gemini.generate_content(
        request.systemInstruction,
        request.contents,
        generation_config,
    )
    return ChatResponse(answer=answer or "Gemini 응답에 텍스트가 없습니다.")
