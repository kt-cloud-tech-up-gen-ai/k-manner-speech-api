"""시나리오별 persona 시작 발화를 추가한다.

Revision ID: e2f6a9c14d80
Revises: c7e1a4b92d60
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f6a9c14d80"
down_revision: Union[str, Sequence[str], None] = "c7e1a4b92d60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 운영 Supabase에는 관리 API migration으로 먼저 반영될 수 있다. 그 뒤 Alembic
    # 계보를 따라와도 중복 컬럼으로 실패하지 않게 PostgreSQL에서는 멱등 DDL을 쓴다.
    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE scenarios ADD COLUMN IF NOT EXISTS opening_line TEXT")
    else:
        with op.batch_alter_table("scenarios", schema=None) as batch_op:
            batch_op.add_column(sa.Column("opening_line", sa.Text(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE scenarios SET opening_line = :opening_line "
            "WHERE id IN (:scenario_id, :legacy_scenario_id)"
        ).bindparams(
            opening_line="안녕하세요. 혹시 어디 찾고 계세요?",
            scenario_id="campus_directions_senior",
            legacy_scenario_id="campus_directions",
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("scenarios", schema=None) as batch_op:
        batch_op.drop_column("opening_line")
