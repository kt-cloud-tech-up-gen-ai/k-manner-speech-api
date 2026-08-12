"""Supabase 운영 DB 확장 스키마를 Alembic 계보로 복원한다.

Revision ID: a1c4e8f52b70
Revises: e7a2f4c81b09
Create Date: 2026-08-12

이 리비전 ID는 이미 운영 Supabase ``alembic_version``에 기록되어 있지만 기존
저장소에는 파일이 없었다. 운영 DB에서는 이미 적용된 것으로 취급되고, 새 DB에서는
동일한 스키마를 재현한다.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c4e8f52b70"
down_revision: Union[str, Sequence[str], None] = "e7a2f4c81b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable_rls() -> None:
    if not _is_postgresql():
        return

    for table in (
        "alembic_version",
        "chat_feedbacks",
        "chat_message_feedbacks",
        "chat_messages",
        "chat_rooms",
        "persona_scenarios",
        "personas",
        "scenarios",
        "user_learning_goals",
        "user_profiles",
        "user_tutorial_progress",
    ):
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))

    op.execute(
        """CREATE POLICY kms_chat_rooms_owner_all ON chat_rooms
        FOR ALL TO authenticated
        USING (auth.uid()::text = user_id::text)
        WITH CHECK (auth.uid()::text = user_id::text)"""
    )
    for table, room_column in (
        ("chat_messages", "chat_messages.room_id"),
        ("chat_feedbacks", "chat_feedbacks.room_id"),
    ):
        # table과 room_column은 바로 위의 고정 리터럴만 사용한다.
        policy_sql = f"""CREATE POLICY kms_{table}_owner_all ON {table}
            FOR ALL TO authenticated
            USING (EXISTS (
                SELECT 1 FROM chat_rooms
                WHERE chat_rooms.id::text = {room_column}::text
                  AND chat_rooms.user_id::text = auth.uid()::text
            ))
            WITH CHECK (EXISTS (
                SELECT 1 FROM chat_rooms
                WHERE chat_rooms.id::text = {room_column}::text
                  AND chat_rooms.user_id::text = auth.uid()::text
            ))"""  # noqa: S608
        op.execute(
            sa.text(policy_sql)
        )
    for table in ("personas", "scenarios", "persona_scenarios"):
        op.execute(
            sa.text(
                f"""CREATE POLICY kms_{table}_authenticated_read ON {table}
                FOR SELECT TO authenticated USING (true)"""
            )
        )
    for table in ("user_profiles", "user_learning_goals"):
        op.execute(
            sa.text(
                f"""CREATE POLICY kms_{table}_owner_all ON {table}
                FOR ALL TO authenticated
                USING (auth.uid()::text = user_id::text)
                WITH CHECK (auth.uid()::text = user_id::text)"""
            )
        )


def upgrade() -> None:
    with op.batch_alter_table("chat_rooms") as batch_op:
        batch_op.alter_column(
            "user_id", existing_type=sa.String(length=128), nullable=True
        )
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer()))
        batch_op.add_column(
            sa.Column(
                "is_tutorial", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(sa.Column("guest_id", sa.String(length=128)))
        batch_op.create_check_constraint(
            "ck_chat_rooms_exactly_one_owner",
            "(user_id IS NOT NULL AND guest_id IS NULL) OR "
            "(user_id IS NULL AND guest_id IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_chat_rooms_duration_seconds",
            "duration_seconds IS NULL OR duration_seconds >= 0",
        )

    op.create_index(
        "ix_chat_rooms_guest_id_created_at",
        "chat_rooms",
        ["guest_id", "created_at"],
    )
    op.create_index("ix_chat_rooms_persona_id", "chat_rooms", ["persona_id"])
    op.create_index(
        "ix_chat_rooms_scenario_id",
        "chat_rooms",
        ["scenario_id"],
        postgresql_where=sa.text("scenario_id IS NOT NULL"),
        sqlite_where=sa.text("scenario_id IS NOT NULL"),
    )
    op.create_index(
        "ix_chat_rooms_user_completed_at",
        "chat_rooms",
        ["user_id", sa.text("completed_at DESC")],
        postgresql_where=sa.text("completed_at IS NOT NULL"),
        sqlite_where=sa.text("completed_at IS NOT NULL"),
    )

    with op.batch_alter_table("personas") as batch_op:
        batch_op.add_column(sa.Column("headline", sa.String(length=120)))
        batch_op.add_column(sa.Column("avatar_url", sa.Text()))
        batch_op.add_column(
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    op.create_index(
        "ix_personas_active_sort", "personas", ["is_active", "sort_order", "id"]
    )

    with op.batch_alter_table("scenarios") as batch_op:
        batch_op.add_column(sa.Column("title_ko", sa.String(length=160)))
        batch_op.add_column(sa.Column("title_en", sa.String(length=160)))
        batch_op.add_column(sa.Column("difficulty", sa.String(length=16)))
        batch_op.add_column(sa.Column("estimated_minutes", sa.SmallInteger()))
        batch_op.add_column(
            sa.Column(
                "is_featured", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    op.execute(sa.text("UPDATE scenarios SET title_ko = description WHERE title_ko IS NULL"))
    with op.batch_alter_table("scenarios") as batch_op:
        batch_op.alter_column(
            "title_ko", existing_type=sa.String(length=160), nullable=False
        )
    op.create_index(
        "ix_scenarios_active_featured_sort",
        "scenarios",
        ["is_active", "is_featured", "sort_order", "id"],
    )

    with op.batch_alter_table("user_profiles") as batch_op:
        batch_op.add_column(sa.Column("full_name", sa.String(length=100)))
        batch_op.add_column(sa.Column("age", sa.SmallInteger()))
        batch_op.add_column(
            sa.Column(
                "app_language", sa.String(length=5), nullable=False, server_default="ko"
            )
        )
        batch_op.add_column(
            sa.Column("onboarding_completed_at", sa.DateTime(timezone=True))
        )
        batch_op.add_column(sa.Column("time_zone", sa.Text()))
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch_op.add_column(sa.Column("name", sa.String(length=100)))
        batch_op.add_column(
            sa.Column("learning_goal_other", sa.String(length=500))
        )
        batch_op.create_check_constraint(
            "ck_user_profiles_age", "age IS NULL OR (age >= 1 AND age <= 120)"
        )
        batch_op.create_check_constraint(
            "ck_user_profiles_app_language", "app_language IN ('ko', 'en')"
        )
    with op.batch_alter_table("user_learning_goals") as batch_op:
        batch_op.add_column(sa.Column("custom_goal", sa.Text()))

    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.create_check_constraint(
            "ck_chat_messages_role", "role IN ('user', 'assistant')"
        )

    with op.batch_alter_table("chat_feedbacks") as batch_op:
        batch_op.add_column(sa.Column("appropriateness_score", sa.Integer()))
        batch_op.add_column(sa.Column("naturalness_label", sa.String(length=32)))
        batch_op.add_column(sa.Column("summary_comment", sa.Text()))
        batch_op.add_column(sa.Column("suggested_expression", sa.Text()))
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer()))
        batch_op.create_check_constraint(
            "ck_chat_feedbacks_score_range", "score >= 0 AND score <= 100"
        )
        batch_op.create_check_constraint(
            "ck_chat_feedbacks_appropriateness_range",
            "appropriateness_score IS NULL OR "
            "(appropriateness_score >= 0 AND appropriateness_score <= 100)",
        )
        batch_op.create_check_constraint(
            "ck_chat_feedbacks_duration_seconds",
            "duration_seconds IS NULL OR duration_seconds >= 0",
        )
    op.create_index(
        "ix_chat_feedbacks_last_message_id", "chat_feedbacks", ["last_message_id"]
    )

    op.create_table(
        "chat_message_feedbacks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("room_id", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("honorifics_score", sa.Integer(), nullable=False),
        sa.Column("politeness_score", sa.Integer(), nullable=False),
        sa.Column("context_fit_score", sa.Integer(), nullable=False),
        sa.Column("naturalness_score", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("corrected_sentence", sa.Text(), nullable=False),
        sa.Column(
            "strengths",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "improvements",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100", name="chat_message_feedbacks_score_check"
        ),
        sa.CheckConstraint(
            "honorifics_score BETWEEN 0 AND 25",
            name="chat_message_feedbacks_honorifics_score_check",
        ),
        sa.CheckConstraint(
            "politeness_score BETWEEN 0 AND 25",
            name="chat_message_feedbacks_politeness_score_check",
        ),
        sa.CheckConstraint(
            "context_fit_score BETWEEN 0 AND 25",
            name="chat_message_feedbacks_context_fit_score_check",
        ),
        sa.CheckConstraint(
            "naturalness_score BETWEEN 0 AND 25",
            name="chat_message_feedbacks_naturalness_score_check",
        ),
        sa.CheckConstraint(
            "verdict IN ('natural', 'needs_practice')",
            name="chat_message_feedbacks_verdict_check",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["chat_rooms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "model",
            "prompt_version",
            name="uq_message_feedback_model_prompt",
        ),
    )
    op.create_index(
        "ix_chat_message_feedbacks_message_id",
        "chat_message_feedbacks",
        ["message_id"],
    )
    op.create_index(
        "ix_chat_message_feedbacks_room_created",
        "chat_message_feedbacks",
        ["room_id", "created_at"],
    )

    op.create_table(
        "user_tutorial_progress",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "tutorial_key",
            sa.String(length=64),
            nullable=False,
            server_default="first_home",
        ),
        sa.Column(
            "current_step", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "current_step >= 0", name="ck_user_tutorial_progress_step"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profiles.user_id"],
            name="fk_user_tutorial_progress_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "tutorial_key"),
    )

    _enable_rls()


def downgrade() -> None:
    if _is_postgresql():
        for table, policy in (
            ("chat_rooms", "kms_chat_rooms_owner_all"),
            ("chat_messages", "kms_chat_messages_owner_all"),
            ("chat_feedbacks", "kms_chat_feedbacks_owner_all"),
            ("personas", "kms_personas_authenticated_read"),
            ("scenarios", "kms_scenarios_authenticated_read"),
            ("persona_scenarios", "kms_persona_scenarios_authenticated_read"),
            ("user_profiles", "kms_user_profiles_owner_all"),
            ("user_learning_goals", "kms_user_learning_goals_owner_all"),
        ):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))

    op.drop_table("user_tutorial_progress")
    op.drop_index(
        "ix_chat_message_feedbacks_room_created",
        table_name="chat_message_feedbacks",
    )
    op.drop_index(
        "ix_chat_message_feedbacks_message_id",
        table_name="chat_message_feedbacks",
    )
    op.drop_table("chat_message_feedbacks")

    op.drop_index("ix_chat_feedbacks_last_message_id", table_name="chat_feedbacks")
    with op.batch_alter_table("chat_feedbacks") as batch_op:
        batch_op.drop_constraint(
            "ck_chat_feedbacks_duration_seconds", type_="check"
        )
        batch_op.drop_constraint(
            "ck_chat_feedbacks_appropriateness_range", type_="check"
        )
        batch_op.drop_constraint("ck_chat_feedbacks_score_range", type_="check")
        for column in (
            "duration_seconds",
            "suggested_expression",
            "summary_comment",
            "naturalness_label",
            "appropriateness_score",
        ):
            batch_op.drop_column(column)

    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_constraint("ck_chat_messages_role", type_="check")
    with op.batch_alter_table("user_learning_goals") as batch_op:
        batch_op.drop_column("custom_goal")
    with op.batch_alter_table("user_profiles") as batch_op:
        batch_op.drop_constraint("ck_user_profiles_app_language", type_="check")
        batch_op.drop_constraint("ck_user_profiles_age", type_="check")
        for column in (
            "learning_goal_other",
            "name",
            "created_at",
            "time_zone",
            "onboarding_completed_at",
            "app_language",
            "age",
            "full_name",
        ):
            batch_op.drop_column(column)

    op.drop_index("ix_scenarios_active_featured_sort", table_name="scenarios")
    with op.batch_alter_table("scenarios") as batch_op:
        for column in (
            "is_active",
            "sort_order",
            "is_featured",
            "estimated_minutes",
            "difficulty",
            "title_en",
            "title_ko",
        ):
            batch_op.drop_column(column)
    op.drop_index("ix_personas_active_sort", table_name="personas")
    with op.batch_alter_table("personas") as batch_op:
        for column in ("is_active", "sort_order", "avatar_url", "headline"):
            batch_op.drop_column(column)

    op.drop_index("ix_chat_rooms_user_completed_at", table_name="chat_rooms")
    op.drop_index("ix_chat_rooms_scenario_id", table_name="chat_rooms")
    op.drop_index("ix_chat_rooms_persona_id", table_name="chat_rooms")
    op.drop_index("ix_chat_rooms_guest_id_created_at", table_name="chat_rooms")
    with op.batch_alter_table("chat_rooms") as batch_op:
        batch_op.drop_constraint("ck_chat_rooms_duration_seconds", type_="check")
        batch_op.drop_constraint("ck_chat_rooms_exactly_one_owner", type_="check")
        for column in (
            "guest_id",
            "is_tutorial",
            "duration_seconds",
            "completed_at",
            "started_at",
        ):
            batch_op.drop_column(column)
        batch_op.alter_column(
            "user_id", existing_type=sa.String(length=128), nullable=False
        )
