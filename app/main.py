import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import init_db
from app.routers import auth, catalog, chat, health, rooms, voice

logger = logging.getLogger(__name__)


# TODO(KAN-47/monitoring): 에러 추적/알람이 없다. Sentry 등 도입 여부 결정 후
#   여기서 SDK를 초기화하고 5xx 알람을 1개 이상 설정할 것.


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception:
        logger.exception("데이터베이스 초기화에 실패했습니다. DATABASE_URL을 확인하세요.")
    yield


app = FastAPI(title="K-MANNER SPEECH", version="0.0.1", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(catalog.router)
app.include_router(rooms.router)
app.include_router(voice.router)
