"""운영 프로필에 저장된 세부 학습 목적 값을 모델 계보에 맞춘다.

Revision ID: f4a8d1e62c93
Revises: e2f6a9c14d80
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f4a8d1e62c93"
down_revision: Union[str, Sequence[str], None] = "e2f6a9c14d80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GOAL_CHECK = (
    "goal IN ('daily_conversation', 'business', 'travel', 'exam', 'culture', "
    "'work_interview', 'dating_first_impression', 'small_talk', "
    "'requests_refusals', 'service_complaints', 'honorifics', 'other')"
)


def upgrade() -> None:
    with op.batch_alter_table("user_learning_goals", schema=None) as batch_op:
        batch_op.drop_constraint("ck_user_learning_goals_goal", type_="check")
        batch_op.create_check_constraint("ck_user_learning_goals_goal", GOAL_CHECK)


def downgrade() -> None:
    # 새 값이 남아 있으면 제약 축소가 실패하도록 둔다. 조용히 사용자 선택을 지우지 않는다.
    with op.batch_alter_table("user_learning_goals", schema=None) as batch_op:
        batch_op.drop_constraint("ck_user_learning_goals_goal", type_="check")
        batch_op.create_check_constraint(
            "ck_user_learning_goals_goal",
            "goal IN ('daily_conversation', 'business', 'travel', 'exam', 'culture', 'other')",
        )
