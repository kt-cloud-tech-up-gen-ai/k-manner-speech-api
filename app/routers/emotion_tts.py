"""페르소나 답변을 감정 표현 음성으로 변환하는 API."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import get_tts_settings
from app.schemas.emotion_tts import EmotionTtsRequest, EmotionTtsResponse, HealthResponse
from app.services.emotion_tts_pipeline import EmotionTtsService

# 최종 통합 프로젝트와 같은 URL 계약을 유지합니다.
router = APIRouter(prefix="/emotion-tts", tags=["Emotion TTS"])


@lru_cache
def get_tts_service() -> EmotionTtsService:
    """HTTP 연결을 요청마다 다시 만들지 않도록 TTS 서비스를 캐시합니다."""

    return EmotionTtsService(get_tts_settings())


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """라우터 상태만 확인합니다. Gemini까지 호출하는 심층 검사는 아닙니다."""

    return HealthResponse(status="ok")


@router.get("/audio/{filename}", response_class=FileResponse)
def get_generated_audio(filename: str) -> FileResponse:
    """TTS 출력 폴더 바로 아래에 생성된 WAV 파일만 반환한다."""

    if Path(filename).name != filename or not filename.lower().endswith(".wav"):
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다.")
    output_dir = get_tts_settings().output_dir.resolve()
    audio_path = (output_dir / filename).resolve()
    if audio_path.parent != output_dir or not audio_path.is_file():
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다.")
    return FileResponse(audio_path, media_type="audio/wav", filename=filename)


@router.post("/generate", response_model=EmotionTtsResponse)
async def generate_emotion_tts(request: EmotionTtsRequest) -> EmotionTtsResponse:
    """페르소나의 답변 텍스트와 말투 지시를 Gemini TTS WAV로 변환합니다."""

    try:
        # Gemini 동기 호출과 파일 쓰기를 이벤트 루프 밖 작업 스레드에서 실행합니다.
        return await run_in_threadpool(get_tts_service().generate, request)
    # 요청값 문제는 400, Gemini 또는 저장 실패는 외부 처리 실패인 502로 구분합니다.
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
