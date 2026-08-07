"""KAN-16: personas/scenarios 신설, 누락 테이블 추가, chat_rooms 카탈로그 FK

Revision ID: 9c1f4b0a7d52
Revises: 7ea6b68d4729
Create Date: 2026-08-07

세 가지를 한 리비전에서 처리한다.

1. 카탈로그 승격: personas / scenarios 테이블 생성 + `app/prompts/**` YAML 값 시드.
2. 정합성 보정: 모델만 있고 마이그레이션에 없던 chat_feedbacks / user_profiles /
   user_learning_goals 생성. (지금까지 create_all에 의존하고 있었다.)
3. chat_rooms.persona_id·scenario_id에 카탈로그 FK(RESTRICT) 추가.

3번 전에 고아 참조를 검사한다. 카탈로그에 없는 persona_id/scenario_id를 가진 방이
남아 있으면 FK 추가가 실패하므로, 어떤 값이 문제인지 먼저 드러내고 중단한다.
어떻게 정리할지(시드 추가 / 방 삭제)는 사람이 판단할 몫이다.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c1f4b0a7d52"
down_revision: Union[str, Sequence[str], None] = "7ea6b68d4729"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 시드 행의 version. 마이그레이션은 재현 가능해야 하므로 실행 시각이 아니라 상수를 쓴다.
SEEDED_AT = "2026-08-07 00:00:00+00:00"

# 카탈로그 초기 데이터. 이 상수가 곧 출처이며, 이후 변경은 새 리비전이나 관리 API로 한다.
# 리비전은 한 번 배포되면 고정이므로 여기 값을 나중에 고쳐서는 안 된다.
PERSONA_SEED = [
    {
        "id": "doyun",
        "first_name": "도윤",
        "age": 22,
        "gender": "male",
        "description": "도윤 / 캠퍼스 훈남 / 처음 만난 또래",
        "relationship_description": "같은 캠퍼스에서 오늘 처음 만난 또래",
        "voice_id": None,
    },
]

SCENARIO_SEED = [
    {
        "id": "interview",
        "description": "면접 상황 대화 연습",
        "time_context": "평일 오전",
        "place_context": "회사 회의실",
        "communication_goal": "면접관의 질문에 존댓말로 끝까지 답한다",
        "end_condition": "면접관이 마무리 인사를 하면 종료",
        "max_turns": 20,
    },
    {
        "id": "roleplay",
        "description": "지정한 캐릭터와의 역할극 대화",
        "time_context": None,
        "place_context": None,
        "communication_goal": "정해진 배역을 유지하며 상황을 끝까지 이어간다",
        "end_condition": "사용자가 역할극 종료를 요청하면 종료",
        "max_turns": 30,
    },
]

GENDER_VALUES = ("male", "female", "other", "prefer_not_to_say")
STUDY_FREQUENCY_VALUES = (
    "daily",
    "five_per_week",
    "three_per_week",
    "twice_per_week",
    "weekly",
)
LEARNING_GOAL_VALUES = (
    "daily_conversation",
    "business",
    "travel",
    "exam",
    "culture",
    "other",
)


def _enum(values: Sequence[str], constraint_name: str) -> sa.Enum:
    """모델의 `app.core.db.enum_column`과 같은 매핑(VARCHAR + CHECK)."""
    return sa.Enum(
        *values,
        name=constraint_name,
        native_enum=False,
        create_constraint=True,
        length=32,
    )


def _assert_no_orphan_references(connection: sa.Connection) -> None:
    for column, table in (("persona_id", "personas"), ("scenario_id", "scenarios")):
        orphans = connection.execute(
            sa.text(
                f"SELECT DISTINCT {column} FROM chat_rooms"
                f" WHERE {column} IS NOT NULL"
                f" AND {column} NOT IN (SELECT id FROM {table})"
            )
        ).scalars().all()
        if orphans:
            raise RuntimeError(
                f"chat_rooms.{column}가 {table}에 없는 값을 참조한다: {sorted(orphans)}. "
                f"{table} 시드를 보강하거나 해당 방을 정리한 뒤 다시 실행하라."
            )


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=64), nullable=False),
        sa.Column("middle_name", sa.String(length=64), nullable=True),
        sa.Column("last_name", sa.String(length=64), nullable=True),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", _enum(GENDER_VALUES, "ck_personas_gender"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("relationship_description", sa.Text(), nullable=False),
        sa.Column("voice_id", sa.String(length=64), nullable=True),
        sa.Column("version", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("time_context", sa.Text(), nullable=True),
        sa.Column("place_context", sa.Text(), nullable=True),
        sa.Column("communication_goal", sa.Text(), nullable=False),
        sa.Column("end_condition", sa.Text(), nullable=False),
        sa.Column("max_turns", sa.Integer(), nullable=False),
        sa.Column("version", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("native_language", sa.String(length=16), nullable=True),
        sa.Column(
            "gender", _enum(GENDER_VALUES, "ck_user_profiles_gender"), nullable=True
        ),
        sa.Column(
            "study_frequency",
            _enum(STUDY_FREQUENCY_VALUES, "ck_user_profiles_study_frequency"),
            nullable=True,
        ),
        sa.Column("push_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "user_learning_goals",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "goal", _enum(LEARNING_GOAL_VALUES, "ck_user_learning_goals_goal"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "goal"),
    )

    op.create_table(
        "chat_feedbacks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("room_id", sa.String(length=32), nullable=False),
        sa.Column("last_message_id", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["chat_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["last_message_id"], ["chat_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "room_id",
            "last_message_id",
            "model",
            "prompt_version",
            name="uq_chat_feedback_context",
        ),
    )
    with op.batch_alter_table("chat_feedbacks", schema=None) as batch_op:
        batch_op.create_index(
            "ix_chat_feedbacks_room_id_created_at", ["room_id", "created_at"], unique=False
        )

    connection = op.get_bind()
    for row in PERSONA_SEED:
        connection.execute(
            sa.text(
                "INSERT INTO personas"
                " (id, first_name, age, gender, description,"
                "  relationship_description, voice_id, version)"
                " VALUES (:id, :first_name, :age, :gender, :description,"
                "  :relationship_description, :voice_id, :version)"
            ),
            {**row, "version": SEEDED_AT},
        )
    for row in SCENARIO_SEED:
        connection.execute(
            sa.text(
                "INSERT INTO scenarios"
                " (id, description, time_context, place_context,"
                "  communication_goal, end_condition, max_turns, version)"
                " VALUES (:id, :description, :time_context, :place_context,"
                "  :communication_goal, :end_condition, :max_turns, :version)"
            ),
            {**row, "version": SEEDED_AT},
        )

    _assert_no_orphan_references(connection)

    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_chat_rooms_persona_id_personas",
            "personas",
            ["persona_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_chat_rooms_scenario_id_scenarios",
            "scenarios",
            ["scenario_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_chat_rooms_scenario_id_scenarios", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_chat_rooms_persona_id_personas", type_="foreignkey")

    with op.batch_alter_table("chat_feedbacks", schema=None) as batch_op:
        batch_op.drop_index("ix_chat_feedbacks_room_id_created_at")
    op.drop_table("chat_feedbacks")

    op.drop_table("user_learning_goals")
    op.drop_table("user_profiles")
    op.drop_table("scenarios")
    op.drop_table("personas")
