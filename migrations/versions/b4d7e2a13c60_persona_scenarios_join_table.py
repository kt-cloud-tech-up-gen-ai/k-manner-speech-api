"""persona ↔ scenario N:N 매핑 테이블 추가

Revision ID: b4d7e2a13c60
Revises: 9c1f4b0a7d52
Create Date: 2026-08-08

한 상대와 여러 상황을 연습할 수 있고 같은 상황을 여러 상대와 연습할 수 있으므로,
"이 상대로 고를 수 있는 시나리오"를 별도 표로 둔다. 이 표에 없는 조합은 채팅방 생성이
거부되는 값이라, 기존 카탈로그 조합을 그대로 시드해 현재 동작을 유지한다.

FK는 chat_rooms와 같은 RESTRICT다. 카탈로그 행이 사라지면 이 매핑이 가리킬 곳이 없어진다.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d7e2a13c60"
down_revision: Union[str, Sequence[str], None] = "9c1f4b0a7d52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 9c1f4b0a7d52가 넣은 카탈로그의 모든 조합. 지금은 persona가 하나뿐이라 전조합이다.
PAIR_SEED = [
    ("doyun", "interview"),
    ("doyun", "roleplay"),
]


def upgrade() -> None:
    op.create_table(
        "persona_scenarios",
        sa.Column("persona_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("persona_id", "scenario_id"),
    )

    for persona_id, scenario_id in PAIR_SEED:
        # 값을 문장에 묶어 둔다. `op.get_bind().execute(text, params)` 형태는 오프라인
        # (`alembic upgrade --sql`)에서 파라미터가 바인딩되지 않아 VALUES (NULL, NULL)로
        # 렌더된다. 실제로 확인한 동작이다.
        op.execute(
            sa.text(
                "INSERT INTO persona_scenarios (persona_id, scenario_id)"
                " VALUES (:persona_id, :scenario_id)"
            ).bindparams(persona_id=persona_id, scenario_id=scenario_id)
        )


def downgrade() -> None:
    op.drop_table("persona_scenarios")
