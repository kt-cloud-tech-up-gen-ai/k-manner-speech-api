"""브라우저 Web Speech API 테스트 화면을 제공한다."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["Web Speech Test"])
WEB_SPEECH_PAGE = Path(__file__).resolve().parent.parent / "static" / "web_speech_test.html"


@router.get("/web-speech-test", include_in_schema=False)
def web_speech_test_page() -> FileResponse:
    """마이크로 Web Speech STT를 확인하는 정적 HTML을 반환한다."""

    return FileResponse(WEB_SPEECH_PAGE, media_type="text/html")
