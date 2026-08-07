"""HTTP 요청/응답 DTO.

SQLAlchemy 엔티티(`app/models/`)와 의도적으로 분리한다. 엔티티는 DB 테이블의 모양이고
여기 있는 것은 API 계약의 모양이라, 둘은 서로 다른 속도로 변한다.

모듈은 라우터와 1:1로 대응한다(`schemas/rooms.py` ↔ `routers/rooms.py`).

## 네이밍 규칙

- 요청 본문은 `...Request`, 응답 본문은 `...Response`로 끝낸다.
  접미사 어휘 자체에 업계 표준은 없다(공식 템플릿은 `UserPublic`, FastAPI Users는
  `UserRead`를 쓴다). 저장소 안에서 일관되기만 하면 되고, 이 저장소는 Request/Response다.
- 이름 앞부분은 대응하는 도메인 모델 이름을 그대로 쓴다.
  `ChatMessage`(models/chat.py) → `ChatMessageResponse`.
  단순히 `MessageResponse`라고 하면 "메시지를 담은 응답"인지 "범용 응답 래퍼"인지
  구분되지 않는다.
- 목록 응답은 단건 응답 이름 + `List`.
  `ChatMessageResponse` → `ChatMessageListResponse`.
- `...Item` 같은 별도 어휘는 쓰지 않는다. 목록의 원소도 그냥 응답 DTO다.

`CreateRoomRequest` / `SendMessageRequest`처럼 동사가 앞에 오는 이름이 남아 있는데,
이는 해당 엔드포인트가 리소스 조회가 아니라 행위에 가까워 의도적으로 둔 것이다.
새 DTO를 만들 때는 리소스 이름을 앞에 두는 쪽을 기본으로 한다.

## 여기 두지 않는 것

DB에 직렬화되어 저장되는 모델은 API DTO가 아니라 **영속 계약**이므로 서비스 계층이
소유한다. 예: `FeedbackResult`/`CategoryScores`/`FeedbackIssue`는
`chat_feedbacks.result_json`에 저장되고 되읽히므로 `app/services/feedback.py`에 있다.
HTTP 응답인 `FeedbackResponse`만 여기 두고 그것들을 임베드한다.
"""
