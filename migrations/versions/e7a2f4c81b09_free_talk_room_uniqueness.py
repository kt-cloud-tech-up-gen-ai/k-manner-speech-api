"""자유 수다 방을 사용자-persona 당 하나로 제한

Revision ID: e7a2f4c81b09
Revises: d5b8c07f9a13
Create Date: 2026-08-08

시나리오 없는 방은 "AI와 무한정 수다 떠는" 자유 대화방이다. 같은 상대와 그런 방을 여러 개
가질 이유가 없으므로 사용자-persona 당 하나로 묶는다. persona가 N개면 사용자는 최대 N개.

시나리오가 있는 방은 대상이 아니다. 같은 (사용자, persona)로 면접·역할극·길묻기를 각각
만들 수 있어야 하므로 `WHERE scenario_id IS NULL`이 붙은 **부분** 유니크 인덱스를 쓴다.
WHERE를 빼면 시나리오 방까지 하나로 묶여 버린다.

`sqlite_where`와 `postgresql_where`를 둘 다 준다. 하나만 주면 다른 백엔드에서 WHERE가 빠진
전체 유니크 인덱스가 만들어져, 개발 환경은 멀쩡한데 운영에서 시나리오 방 생성이 막힌다.

## 인덱스를 걸기 전에 중복을 검사하는 이유

이미 중복이 있으면 CREATE UNIQUE INDEX가 실패한다. 그 오류만으로는 어느 방이 문제인지
알 수 없어 대응할 수 없으므로, 먼저 조회해 room_id를 보여 주고 중단한다
(`9c1f4b0a7d52`의 `_assert_no_orphan_references`와 같은 방식). 무엇을 남기고 무엇을 지울지는
사람이 판단할 몫이다.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "e7a2f4c81b09"
down_revision: Union[str, Sequence[str], None] = "d5b8c07f9a13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_chat_rooms_free_talk"
FREE_TALK_ONLY = "scenario_id IS NULL"


def _assert_no_duplicate_free_talk_rooms(connection: sa.Connection) -> None:
    # noqa 사유: 보간하는 FREE_TALK_ONLY는 이 모듈의 상수 문자열이다. 인덱스의 WHERE
    # 절과 한 글자도 어긋나면 안 되는 값이라 일부러 상수를 공유한다.
    duplicates = connection.execute(
        sa.text(
            "SELECT user_id, persona_id, COUNT(*) AS n"  # noqa: S608
            " FROM chat_rooms"
            f" WHERE {FREE_TALK_ONLY}"
            " GROUP BY user_id, persona_id"
            " HAVING COUNT(*) > 1"
        )
    ).all()
    if not duplicates:
        return

    details = []
    for user_id, persona_id, count in duplicates:
        # noqa 사유: 위와 같다. user_id·persona_id는 바인드 파라미터로 넘기고 있고,
        # 보간되는 것은 상수 조건절뿐이다.
        room_ids = connection.execute(
            sa.text(
                "SELECT id FROM chat_rooms"  # noqa: S608
                f" WHERE {FREE_TALK_ONLY}"
                "   AND user_id = :user_id AND persona_id = :persona_id"
                " ORDER BY created_at"
            ),
            {"user_id": user_id, "persona_id": persona_id},
        ).scalars().all()
        details.append(f"(user_id={user_id}, persona_id={persona_id}) {count}건: {room_ids}")

    raise RuntimeError(
        "자유 수다 방이 사용자-persona 당 둘 이상인 곳이 있어 유니크 인덱스를 만들 수 없다.\n"
        + "\n".join(details)
        + "\n남길 방 하나만 두고 나머지를 정리한 뒤 다시 실행하라."
    )


def upgrade() -> None:
    # 오프라인(`alembic upgrade --sql`)에서는 건너뛴다. 그 모드의 connection.execute()는
    # None을 돌려주므로 결과를 읽는 검사가 성립하지 않는다(AttributeError로 죽는다).
    # 대신 만들어진 스크립트를 실제 DB에서 돌릴 때 CREATE UNIQUE INDEX가 실패해 드러난다.
    # 조회 결과가 필요 없는 DDL만 스크립트에 남는다.
    if not context.is_offline_mode():
        _assert_no_duplicate_free_talk_rooms(op.get_bind())

    op.create_index(
        INDEX_NAME,
        "chat_rooms",
        ["user_id", "persona_id"],
        unique=True,
        sqlite_where=sa.text(FREE_TALK_ONLY),
        postgresql_where=sa.text(FREE_TALK_ONLY),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="chat_rooms")
