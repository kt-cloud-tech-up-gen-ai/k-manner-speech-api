"""STT 결과부터 Gemini TTS까지 한 번에 검증하는 통합 API."""

from functools import lru_cache

from fastapi import APIRouter, HTTPException
from google import genai
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings, get_tts_settings
from app.schemas.speech_pipeline import SpeechPipelineRequest, SpeechPipelineResponse
from app.services.emotion_tts_pipeline import EmotionTtsService
from app.services.llm import generate_structured_answer
from app.services.speech_pipeline import SpeechPipelineService
from app.services.user_input_pipeline import UserInputPipelineService
from app.services.user_input_Text import EmotionClassifierService

router = APIRouter(prefix="/speech-pipeline", tags=["Speech Pipeline Test"])


@lru_cache
def get_speech_pipeline_service() -> SpeechPipelineService:
    """프로세스 동안 외부 API 클라이언트와 파이프라인 서비스를 재사용한다."""

    analysis_settings = get_settings()
    analyzer = UserInputPipelineService(
        text_analyzer=EmotionClassifierService(
            genai.Client(api_key=analysis_settings.gemini_api_key),
            analysis_settings.emotion_model,
        )
    )
    return SpeechPipelineService(
        analyzer=analyzer,
        chat_generator=generate_structured_answer,
        tts_service=EmotionTtsService(get_tts_settings()),
    )


@router.post("/generate", response_model=SpeechPipelineResponse)
async def generate_speech_pipeline(
    request: SpeechPipelineRequest,
) -> SpeechPipelineResponse:
    """STT 텍스트를 분석하고 페르소나 답변과 말투를 Gemini 음성으로 만든다."""

    try:
        return await run_in_threadpool(get_speech_pipeline_service().generate, request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
