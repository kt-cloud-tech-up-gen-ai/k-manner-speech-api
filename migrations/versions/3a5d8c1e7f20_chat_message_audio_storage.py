"""persist assistant audio storage path

Revision ID: 3a5d8c1e7f20
Revises: c7e1a4b92d60
"""

import sqlalchemy as sa
from alembic import op

revision = "3a5d8c1e7f20"
down_revision = "c7e1a4b92d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("audio_storage_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "audio_storage_path")
