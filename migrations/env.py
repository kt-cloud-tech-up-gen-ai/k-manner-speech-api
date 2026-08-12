"""Alembic 환경 설정.

DB URL과 메타데이터는 alembic.ini가 아니라 app.core.db에서 가져온다
(애플리케이션과 마이그레이션이 같은 DATABASE_URL을 보도록).
"""

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.core.db import Base, get_database_url
from app.models import catalog, chat, user  # noqa: F401  테이블 등록 목적(autogenerate 인식)
from migrations.autogenerate_filters import include_object

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers 기본값(True)은 앱 로거(app.*)를 꺼뜨린다.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    """alembic.ini/CLI가 URL을 명시하면 그것을, 아니면 앱 설정을 따른다(테스트 주입용)."""
    return config.get_main_option("sqlalchemy.url") or get_database_url()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite는 ALTER를 거의 지원하지 않아 batch 모드가 필요하다(테스트 환경).
        render_as_batch=connection.dialect.name == "sqlite",
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # 테스트가 Connection을 직접 주입할 수 있게 한다.
    connection = config.attributes.get("connection", None)
    if connection is not None:
        _run(connection)
        return

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as conn:
        _run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
