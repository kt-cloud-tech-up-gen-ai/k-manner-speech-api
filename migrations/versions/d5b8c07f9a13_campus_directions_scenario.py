"""campus_directions 시나리오 추가 + 시나리오 턴 상한 마무리 대사 컬럼

Revision ID: d5b8c07f9a13
Revises: c3f1a9d5e274
Create Date: 2026-08-08

첫 실사용 시나리오를 넣는다. persona는 새로 만들지 않고 `9c1f4b0a7d52`가 시드한
`doyun`을 쓴다(관계 설명이 "같은 캠퍼스에서 오늘 처음 만난 또래"라 그대로 맞는다).

## turn_limit_exit_line

`max_turns`에 도달했는데 종료 조건을 채우지 못한 대화도 어딘가에서 끝나야 한다. 그때
persona가 할 말을 시나리오마다 정해 둔다. campus_directions는 "수업 시간이 되어서
가봐야 한다"며 자리를 뜬다. 이 경로로 끝난 방은 `chat_rooms.status = 'failed'`가 된다
(판정과 실제 발화는 애플리케이션 몫이며 이 리비전은 값만 넣는다).

기존 시나리오(interview, roleplay)에는 전용 마무리 대사가 없어 NULL로 남는다. 그래서
컬럼은 nullable이다. 억지로 채우면 없는 기획을 지어내는 셈이 된다.

## 시드 INSERT를 `op.execute(text(...).bindparams(...))`로 쓰는 이유

`op.get_bind().execute(text, params)` 형태는 온라인 실행에서는 정상이지만 오프라인
(`alembic upgrade --sql`)에서 파라미터가 바인딩되지 않아 `VALUES (NULL, NULL, ...)`로
렌더된다. 조용히 잘못된 SQL이 나오므로, 값을 문장에 묶어 두는 `bindparams`를 쓴다.
(선행 리비전 `9c1f4b0a7d52`의 시드 3건은 아직 옛 형태다.)

## `version`에 타입을 명시하는 이유

`bindparams(version="2026-08-08 00:00:00+00:00")`처럼 문자열을 넘기면 SQLAlchemy가 값에서
타입을 VARCHAR로 추론하고, psycopg가 `$N::VARCHAR`로 렌더한다. PostgreSQL은 varchar를
timestamptz로 암묵 변환하지 않으므로 `DatatypeMismatch`로 실패한다(실제로 겪었다).
execute 시점에 파라미터를 넘기는 옛 형태(`9c1f4b0a7d52`)는 타입이 붙지 않아 PostgreSQL이
대상 컬럼에서 추론하기 때문에 우연히 동작했다. bindparams로 옮기면서 드러난 함정이다.

그래서 `datetime` 객체를 `sa.DateTime(timezone=True)`로 명시해 바인딩한다. 문자열에
타입만 붙이면 SQLite가 거부하므로(`SQLite DateTime type only accepts Python datetime`),
값도 문자열이 아니라 `datetime`이어야 한다.
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5b8c07f9a13"
down_revision: Union[str, Sequence[str], None] = "c3f1a9d5e274"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 9c1f4b0a7d52와 같은 규칙: 실행 시각이 아니라 상수를 쓴다(재현 가능해야 하므로).
SEEDED_AT = datetime(2026, 8, 8, tzinfo=timezone.utc)

SCENARIO_ID = "campus_directions"
PERSONA_ID = "doyun"

SCENARIO_SEED = {
    "id": SCENARIO_ID,
    "description": "캠퍼스에서 처음 만난 또래에게 교무처 위치를 묻는 대화",
    "time_context": "평일 오후",
    "place_context": "캠퍼스 중앙 광장",
    "communication_goal": "교무처 위치를 정중하게 묻고 안내를 끝까지 확인한다",
    "end_condition": "교무처 위치를 안내받고 감사 인사를 하면 종료",
    "max_turns": 10,
    "turn_limit_exit_line": "미안, 나 수업 시간이 다 돼서 가봐야 할 것 같아.",
}


def upgrade() -> None:
    with op.batch_alter_table("scenarios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("turn_limit_exit_line", sa.Text(), nullable=True))

    op.execute(
        sa.text(
            "INSERT INTO scenarios"
            " (id, description, time_context, place_context, communication_goal,"
            "  end_condition, max_turns, turn_limit_exit_line, version)"
            " VALUES (:id, :description, :time_context, :place_context,"
            "  :communication_goal, :end_condition, :max_turns, :turn_limit_exit_line,"
            "  :version)"
        ).bindparams(
            sa.bindparam("version", SEEDED_AT, type_=sa.DateTime(timezone=True)),
            **SCENARIO_SEED,
        )
    )
    # 이 조합이 없으면 시나리오가 존재해도 사용자가 고를 수 없다.
    op.execute(
        sa.text(
            "INSERT INTO persona_scenarios (persona_id, scenario_id)"
            " VALUES (:persona_id, :scenario_id)"
        ).bindparams(persona_id=PERSONA_ID, scenario_id=SCENARIO_ID)
    )


def downgrade() -> None:
    # 매핑이 먼저다. scenarios를 먼저 지우면 FK(RESTRICT)에 걸린다.
    op.execute(
        sa.text("DELETE FROM persona_scenarios WHERE scenario_id = :id").bindparams(
            id=SCENARIO_ID
        )
    )
    op.execute(sa.text("DELETE FROM scenarios WHERE id = :id").bindparams(id=SCENARIO_ID))

    with op.batch_alter_table("scenarios", schema=None) as batch_op:
        batch_op.drop_column("turn_limit_exit_line")
