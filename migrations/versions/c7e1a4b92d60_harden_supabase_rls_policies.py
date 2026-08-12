"""Supabase Data API 권한과 소유권 RLS 정책을 강화한다.

Revision ID: c7e1a4b92d60
Revises: b6d9f4e81a32
"""

from alembic import op

revision = "c7e1a4b92d60"
down_revision = "b6d9f4e81a32"
branch_labels = None
depends_on = None

CATALOG_TABLES = ("personas", "scenarios", "persona_scenarios")
OWNED_TABLES = (
    "user_profiles",
    "user_learning_goals",
    "chat_rooms",
    "chat_messages",
    "chat_feedbacks",
)


def _is_postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _execute(statement: str) -> None:
    op.execute(statement)


def _replace_all_policy(table: str, predicate: str) -> None:
    policy = f"kms_{table}_owner_all"
    _execute(f'DROP POLICY IF EXISTS "{policy}" ON public.{table}')
    _execute(
        f'CREATE POLICY "{policy}" ON public.{table} '
        f"FOR ALL TO authenticated USING ({predicate}) WITH CHECK ({predicate})"
    )


def upgrade() -> None:
    if not _is_postgresql():
        return

    # AC-RLS-OWNERSHIP-MATRIX: 브라우저 역할은 아래 권한과 소유권 정책만 사용한다.
    all_tables = ", ".join(f"public.{table}" for table in (*CATALOG_TABLES, *OWNED_TABLES))
    _execute(f"REVOKE ALL PRIVILEGES ON TABLE {all_tables} FROM anon, authenticated")

    for table in (*CATALOG_TABLES, *OWNED_TABLES):
        _execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")

    _execute(
        "GRANT SELECT ON TABLE public.personas, public.scenarios, "
        "public.persona_scenarios TO authenticated"
    )
    for table in CATALOG_TABLES:
        policy = f"kms_{table}_authenticated_read"
        _execute(f'DROP POLICY IF EXISTS "{policy}" ON public.{table}')
        _execute(
            f'CREATE POLICY "{policy}" ON public.{table} '
            "FOR SELECT TO authenticated USING (auth.uid() IS NOT NULL)"
        )

    owned_tables = ", ".join(f"public.{table}" for table in OWNED_TABLES)
    _execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {owned_tables} TO authenticated")
    _replace_all_policy("user_profiles", "auth.uid()::text = user_id")
    _replace_all_policy("user_learning_goals", "auth.uid()::text = user_id")
    _replace_all_policy("chat_rooms", "auth.uid()::text = user_id")

    message_owner = (
        "EXISTS (SELECT 1 FROM public.chat_rooms "
        "WHERE chat_rooms.id = chat_messages.room_id "
        "AND chat_rooms.user_id = auth.uid()::text)"
    )
    _replace_all_policy("chat_messages", message_owner)

    feedback_owner = (
        "EXISTS (SELECT 1 FROM public.chat_rooms "
        "WHERE chat_rooms.id = chat_feedbacks.room_id "
        "AND chat_rooms.user_id = auth.uid()::text)"
    )
    _replace_all_policy("chat_feedbacks", feedback_owner)


def downgrade() -> None:
    if not _is_postgresql():
        return

    for table in CATALOG_TABLES:
        _execute(f'DROP POLICY IF EXISTS "kms_{table}_authenticated_read" ON public.{table}')
    for table in OWNED_TABLES:
        _execute(f'DROP POLICY IF EXISTS "kms_{table}_owner_all" ON public.{table}')

    all_tables = ", ".join(f"public.{table}" for table in (*CATALOG_TABLES, *OWNED_TABLES))
    _execute(f"REVOKE ALL PRIVILEGES ON TABLE {all_tables} FROM anon, authenticated")
