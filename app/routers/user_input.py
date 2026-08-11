"""텍스트의 감정·표현 방식·의도를 분석하는 API."""

from functools import lru_cache
from time import perf_counter

from fastapi import APIRouter, HTTPException
from google import genai
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.schemas.user_input import TextUserInputRequest, UserInputAnalysis
from app.services.user_input_Text import EmotionClassifierService
from app.services.user_input_pipeline import UserInputPipelineService

router = APIRouter(prefix="/user-input", tags=["User Input Analysis"])


@lru_cache
def get_text_analyzer() -> EmotionClassifierService:
    settings = get_settings()
    return EmotionClassifierService(
        genai.Client(api_key=settings.gemini_api_key), settings.emotion_model
    )


@lru_cache
def get_text_input_service() -> UserInputPipelineService:
    return UserInputPipelineService(text_analyzer=get_text_analyzer())


@router.post("/text", response_model=UserInputAnalysis)
async def analyze_text_input(request: TextUserInputRequest) -> UserInputAnalysis:
    started_at = perf_counter()
    try:
        result = await run_in_threadpool(get_text_input_service().analyze_text, request.text)
        return result.model_copy(
            update={"processing_time_ms": round((perf_counter() - started_at) * 1_000, 2)}
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
