"""chat_rooms: rename title to name, add activity timestamps

title -> name 은 데이터를 보존하는 리네임이다(drop/add 아님).
NOT NULL 승격 전에 백필한다:
  - name: COALESCE(title, '대화')
  - updated_at / last_message_at: created_at

Revision ID: 7ea6b68d4729
Revises: 5462e05b82eb
Create Date: 2026-08-06 17:26:36.763595

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7ea6b68d4729'
down_revision: Union[str, Sequence[str], None] = '5462e05b82eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_chat_rooms_user_id_last_message_at"


def upgrade() -> None:
    # 1) title -> name 리네임 (값 보존, 아직 nullable)
    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.alter_column(
            "title",
            new_column_name="name",
            existing_type=sa.String(length=200),
            existing_nullable=True,
        )
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_message_preview", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True)
        )

    # 2) NOT NULL 승격 전 백필
    op.execute("UPDATE chat_rooms SET name = COALESCE(name, '대화')")
    op.execute("UPDATE chat_rooms SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute(
        "UPDATE chat_rooms SET last_message_at = created_at WHERE last_message_at IS NULL"
    )

    # 3) NOT NULL 승격 + 정렬용 인덱스
    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.alter_column(
            "name", existing_type=sa.String(length=200), nullable=False
        )
        batch_op.alter_column(
            "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )
        batch_op.alter_column(
            "last_message_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )
        batch_op.create_index(INDEX_NAME, ["user_id", "last_message_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("chat_rooms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME)
        batch_op.drop_column("last_read_at")
        batch_op.drop_column("last_message_preview")
        batch_op.drop_column("last_message_at")
        batch_op.drop_column("updated_at")
        batch_op.alter_column(
            "name",
            new_column_name="title",
            existing_type=sa.String(length=200),
            existing_nullable=False,
            nullable=True,
        )
