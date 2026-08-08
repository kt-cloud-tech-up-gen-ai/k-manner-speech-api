"""chat_rooms에 진행 상태(status)와 턴 수(turn_count) 추가

Revision ID: c3f1a9d5e274
Revises: b4d7e2a13c60
Create Date: 2026-08-08

## 백필

기존 방도 진행 상태를 가져야 한다. 두 값을 대화 이력에서 되살린다.

- `turn_count`: assistant 메시지 수. user 발화와 persona 응답이 모두 저장된 왕복 1회를
  1턴으로 세므로, 응답이 저장된 횟수가 곧 턴 수다.
- `status`: 기본은 `in_progress`. 단 시나리오가 있고 이미 `max_turns`에 도달한 방은
  `completed`로 둔다. 이 보정을 빼면 "턴 수는 상한을 넘었는데 상태는 진행 중"인 방이
  남아, 애플리케이션이 세우는 불변식(max_turns 도달 = 종료)과 어긋난다.

`server_default`는 두지 않는다. 모델(`app/models/chat.py`)이 파이썬 쪽 default만 갖고
있어 DB에 기본값을 남기면 양쪽이 어긋난다. 대신 7ea6b68d4729와 같은 순서를 따른다 —
nullable로 추가 → 백필 → NOT NULL 승격.

## CHECK 제약

`status`는 `sa.String(32)`로 추가하고 제약은 `create_check_constraint`로 **한 번만**
만든다. `enum_column`(= `create_constraint=True`)으로 컬럼을 추가하면서 제약을 또 만들면
같은 이름의 제약이 두 개가 되어 PostgreSQL에서 실패한다. 제약식은 모델이 생성하는 DDL과
글자까지 같아야 한다(`app/core/db.py:enum_column`이 소문자 `.value`를 저장).

autogenerate는 CHECK 제약을 비교하지 않으므로(`migrations/autogenerate_filters.py`),
이 제약이 통째로 빠져도 스키마 정합성 테스트는 통과한다. 실제 DB에 잘못된 값을 넣어 보는
테스트(`tests/test_migrations.py`)만이 이 제약의 존재를 지킨다.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1a9d5e274"
down_revision: Union[str, Sequence[str], None] = "b4d7e2a13c60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_CONSTRAINT = "ck_chat_rooms_status"
STATUS_CHECK = "status IN ('in_progress', 'completed', 'failed', 'abandoned')"


def upgrade() -> None:
    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("turn_count", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE chat_rooms SET turn_count = ("
        "  SELECT COUNT(*) FROM chat_messages"
        "  WHERE chat_messages.room_id = chat_rooms.id"
        "    AND chat_messages.role = 'assistant'"
        ")"
    )
    op.execute("UPDATE chat_rooms SET status = 'in_progress'")
    # `scenario_id IS NOT NULL`은 의도를 드러내기 위한 것이고 동작에는 영향이 없다.
    # scenario_id가 NULL이면 하위 질의도 NULL이라 `turn_count >= NULL`이 참이 되지 않는다
    # (조건을 지워도 결과가 같음을 확인했다). 지우면 세 값 논리에 의존하는 코드가 된다.
    op.execute(
        "UPDATE chat_rooms SET status = 'completed'"
        " WHERE scenario_id IS NOT NULL"
        "   AND turn_count >= ("
        "     SELECT max_turns FROM scenarios WHERE scenarios.id = chat_rooms.scenario_id"
        "   )"
    )

    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.alter_column(
            "status", existing_type=sa.String(length=32), nullable=False
        )
        batch_op.alter_column("turn_count", existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(STATUS_CONSTRAINT, STATUS_CHECK)


def downgrade() -> None:
    # CHECK가 status를 참조하므로 컬럼보다 먼저 지운다.
    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.drop_constraint(STATUS_CONSTRAINT, type_="check")
        batch_op.drop_column("turn_count")
        batch_op.drop_column("status")
