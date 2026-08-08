import os
from collections.abc import Iterator
from enum import Enum
from functools import lru_cache

from sqlalchemy import Engine, Enum as SAEnum, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = ""


def get_database_url() -> str:
    return os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


class Base(DeclarativeBase):
    pass


def enum_column(enum_type: type[Enum], constraint_name: str) -> SAEnum:
    """Enum을 VARCHAR + CHECK 제약으로 매핑한다.

    - native_enum=False: DB 네이티브 enum 타입을 만들지 않는다.
      PostgreSQL 네이티브 enum은 값 추가에 ALTER TYPE이 필요해 마이그레이션이 번거롭다.
    - name: native_enum=False에서는 CHECK 제약 이름이 된다.
    - values_callable: 저장 문자열을 멤버 이름(MALE)이 아니라 값(male)으로 고정한다.
      이 값이 그대로 API 요청/응답에 쓰인다.
    """
    return SAEnum(
        enum_type,
        name=constraint_name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda enum: [member.value for member in enum],
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """엔진은 첫 사용 시점에 만든다(임포트만으로 DB 드라이버를 요구하지 않도록)."""
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


# 애플리케이션에서 스키마를 만드는 함수는 두지 않는다. 테이블 생성·변경은 Alembic만 한다
# (이유는 app/main.py 상단 주석). 테스트는 자기 엔진에 직접 `Base.metadata.create_all`을
# 부르므로 여기에 헬퍼가 필요하지 않다.


def get_db() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
