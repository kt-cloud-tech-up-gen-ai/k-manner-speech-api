"""profile extension and guest room ownership

Revision ID: f8b3c9d21a40
Revises: e7a2f4c81b09
"""

import sqlalchemy as sa
from alembic import context, op

revision = "f8b3c9d21a40"
down_revision = "e7a2f4c81b09"
branch_labels = None
depends_on = None


def _profile_columns() -> dict[str, dict]:
    if context.is_offline_mode():
        return {}
    return {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("user_profiles")
    }


def upgrade() -> None:
    profile_columns = _profile_columns()
    existing_age = profile_columns.get("age")
    if existing_age is not None and (
        not isinstance(existing_age["type"], sa.Integer) or not existing_age["nullable"]
    ):
        raise RuntimeError("existing user_profiles.age is incompatible")

    with op.batch_alter_table("user_profiles") as batch:
        if "name" not in profile_columns:
            batch.add_column(sa.Column("name", sa.String(100), nullable=True))
        if "age" not in profile_columns:
            batch.add_column(sa.Column("age", sa.Integer(), nullable=True))
        if "learning_goal_other" not in profile_columns:
            batch.add_column(
                sa.Column("learning_goal_other", sa.String(500), nullable=True)
            )
    with op.batch_alter_table("chat_rooms") as batch:
        batch.alter_column("user_id", existing_type=sa.String(128), nullable=True)
        batch.add_column(sa.Column("guest_id", sa.String(128), nullable=True))
        batch.create_check_constraint(
            "ck_chat_rooms_exactly_one_owner",
            "(user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL)",
        )
        batch.create_index("ix_chat_rooms_guest_id_created_at", ["guest_id", "created_at"])


def downgrade() -> None:
    with op.batch_alter_table("chat_rooms") as batch:
        batch.drop_index("ix_chat_rooms_guest_id_created_at")
        batch.drop_constraint("ck_chat_rooms_exactly_one_owner", type_="check")
        batch.drop_column("guest_id")
        batch.alter_column("user_id", existing_type=sa.String(128), nullable=False)
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("learning_goal_other")
        batch.drop_column("age")
        batch.drop_column("name")
