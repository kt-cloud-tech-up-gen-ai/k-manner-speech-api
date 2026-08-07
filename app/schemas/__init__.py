"""HTTP 요청/응답 DTO.

SQLAlchemy 엔티티(`app/models/`)와 의도적으로 분리한다. 엔티티는 DB 테이블의 모양이고
여기 있는 것은 API 계약의 모양이라, 둘은 서로 다른 속도로 변한다.

모듈은 라우터와 1:1로 대응한다(`schemas/rooms.py` ↔ `routers/rooms.py`).
"""
