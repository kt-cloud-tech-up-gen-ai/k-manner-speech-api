
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, CurrentUser
from app.core.db import get_db
from app.models.chat import ChatMessage, ChatRoom
from app.schemas.rooms import (
    ChatMessageResponse,
    CreateRoomRequest,
    RoomListResponse,
    RoomResponse,
)
from app.services import catalog

router = APIRouter(tags=["rooms"])

# 이 라우터의 모든 엔드포인트는 로그인이 필요하다. 방 주인은 토큰이 정하고,
# room_id로 접근하는 엔드포인트는 _get_room_or_404가 소유자까지 확인한다.
# TODO(KAN-47/scale): 채팅방 목록·채팅 내역에 페이지네이션이 없다. 대화가 길어지면
#   전체 메시지를 한 번에 반환하므로 limit/cursor 파라미터가 필요하다.


def _get_room_or_404(db: Session, room_id: str, user: AuthUser) -> ChatRoom:
    """내 방만 돌려준다. 남의 방은 없는 것과 같게 취급한다.

    "없는 방"과 "남의 방"에 같은 404를 주는 것은 의도적이다. 403으로 나누면 응답만으로
    그 room_id가 실재한다는 사실을 알려 주게 되고, id를 훑어 남의 방 존재를 확인할 수 있다.
    """
    room = db.get(ChatRoom, room_id)
    if room is None or room.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="채팅방을 찾을 수 없습니다."
        )
    return room


def _reject_duplicate_free_talk_room(db: Session, user_id: str, persona_id: str) -> None:
    """자유 수다 방은 사용자-persona 당 하나뿐이다. 이미 있으면 409로 막는다.

    기존 방을 그냥 돌려주지 않는 이유는 요청의 `name`이 조용히 무시되기 때문이다.
    대신 room_id를 알려 줘 클라이언트가 그 방으로 들어가게 한다.
    """
    existing = db.scalar(
        select(ChatRoom.id).where(
            ChatRoom.user_id == user_id,
            ChatRoom.persona_id == persona_id,
            ChatRoom.scenario_id.is_(None),
        )
    )
    if existing is None:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"이미 이 상대와의 자유 대화방이 있습니다: room_id={existing}."
            " 시나리오 없는 방은 상대마다 하나만 만들 수 있습니다."
        ),
    )


def _to_room_response(room: ChatRoom) -> RoomResponse:
    return RoomResponse(
        id=room.id,
        user_id=room.user_id,
        persona_id=room.persona_id,
        scenario_id=room.scenario_id,
        name=room.name,
        created_at=room.created_at,
    )


def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    request: CreateRoomRequest, user: CurrentUser, db: Session = Depends(get_db)
) -> RoomResponse:
    """채팅방을 생성한다. (KAN-60)

    방 주인은 토큰의 사용자다. 본문으로 받지 않으므로 남의 이름으로 방을 만들 수 없다.

    persona_id·scenario_id는 조회한 카탈로그 행의 id로 저장한다. 요청 값을 그대로 넣으면
    대소문자가 다른 값("Doyun")이 들어가 FK를 위반한다.
    """
    persona = catalog.find_persona(db, request.persona_id)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"알 수 없는 persona입니다: {request.persona_id}",
        )

    scenario = None
    if request.scenario_id:
        scenario = catalog.find_scenario(db, request.scenario_id)
        if scenario is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"알 수 없는 시나리오입니다: {request.scenario_id}",
            )
        # 준비되지 않은 조합으로 방을 만들면 프롬프트가 성립하지 않는다.
        # scenario_id가 없으면 조합 자체가 없으므로 검사하지 않는다.
        if not catalog.is_paired(db, persona.id, scenario.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"고를 수 없는 조합입니다: persona={persona.id},"
                    f" scenario={scenario.id}."
                    f" GET /personas/{persona.id} 의 scenarios 목록에서 고르세요."
                ),
            )

    room = ChatRoom(
        user_id=user.id,
        persona_id=persona.id,
        scenario_id=scenario.id if scenario else None,
        name=request.name,
    )
    db.add(room)
    try:
        db.commit()
    except IntegrityError:
        # 자유 수다 방 중복은 유니크 인덱스가 막는다. 미리 조회해 두는 사전 검사는 두지
        # 않는다 — 조회와 INSERT 사이에 다른 요청이 끼어들 수 있어 어차피 여기가 필요하고,
        # 두 경로가 같은 답을 내므로 사전 검사는 지워도 동작이 변하지 않는다(확인함).
        #
        # 시나리오가 있는 방의 IntegrityError는 이 제약과 무관하므로 손대지 않는다.
        # 구분하지 않으면 FK 위반 같은 다른 오류에 "자유 대화방이 이미 있다"고 답하게 된다.
        db.rollback()
        if scenario is None:
            _reject_duplicate_free_talk_room(db, user.id, persona.id)
        raise
    return _to_room_response(room)


@router.get("/rooms", response_model=RoomListResponse)
def list_rooms(user: CurrentUser, db: Session = Depends(get_db)) -> RoomListResponse:
    """내 채팅방 목록을 최신순으로 반환한다. (KAN-61)

    누구의 목록인지는 토큰이 정한다. 예전에는 `?user_id=`를 받았는데, 그러면 남의 id만
    알면 그 사람의 방 목록을 그대로 조회할 수 있었다.
    """
    rooms = db.scalars(
        select(ChatRoom)
        .where(ChatRoom.user_id == user.id)
        .order_by(ChatRoom.created_at.desc())
    ).all()
    return RoomListResponse(rooms=[_to_room_response(room) for room in rooms])


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: str, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    """내 채팅방을 지운다.

    대화 내역과 피드백도 함께 사라진다(모델의 cascade). 되돌릴 수 없다 — 숨김 처리가
    아니라 실제 삭제다.

    자유 수다 방을 지우면 그 상대의 자리가 비므로 같은 상대로 다시 만들 수 있다.

    남의 방이나 없는 방은 똑같이 404다. 성공은 본문 없이 204.
    """
    db.delete(_get_room_or_404(db, room_id, user))
    db.commit()
