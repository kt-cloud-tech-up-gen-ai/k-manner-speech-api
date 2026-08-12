from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_cors_allow_origins
from app.routers import auth, catalog, chat, health, rooms, web_speech
from app.routers.room_conversation import router as room_conversation_router

# 기동 시 스키마를 만들지 않는다. 스키마의 유일한 출처는 Alembic이다(`alembic upgrade head`).
#
# 예전에는 여기서 create_all을 불렀다. create_all은 **없는 테이블만 만들고 기존 테이블은
# 고치지 않는다.** 그래서 서버를 먼저 띄운 DB에는 옛 모델로 만들어진 테이블이 그대로 굳고,
# 나중 기동이 새 테이블만 덧붙여, alembic_version도 없이 리비전이 뒤섞인 스키마가 남는다.
# 그 DB에 `alembic upgrade head`를 걸면 baseline부터 돌기 때문에 DuplicateTable로 죽는다.
# 실제로 그렇게 깨졌다(chat_rooms는 baseline에 동결, personas는 존재, 시드는 0행).

# TODO(KAN-47/monitoring): 에러 추적/알람이 없다. Sentry 등 도입 여부 결정 후
#   기동 훅에서 SDK를 초기화하고 5xx 알람을 1개 이상 설정할 것.

app = FastAPI(title="K-MANNER SPEECH", version="0.0.1")

# 프론트(:5173)와 API(:8000)는 출처가 다르다. preflight(OPTIONS)에 허용 헤더를 내려주지 않으면
# 브라우저가 실제 요청 자체를 보내지 않는다. DELETE /rooms/{id}와 Authorization 헤더를 쓰므로
# 메서드/헤더를 모두 허용한다. allow_credentials=True 이므로 출처는 와일드카드가 아닌 명시 목록이어야 한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(catalog.router)
app.include_router(rooms.router)
app.include_router(web_speech.router)
app.include_router(room_conversation_router)
