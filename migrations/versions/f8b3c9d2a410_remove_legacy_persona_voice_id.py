"""사용하지 않는 ElevenLabs persona voice_id 제거

Revision ID: f8b3c9d2a410
Revises: e7a2f4c81b09
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8b3c9d2a410"
down_revision: Union[str, Sequence[str], None] = "e7a2f4c81b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("personas", "voice_id")


def downgrade() -> None:
    op.add_column(
        "personas", sa.Column("voice_id", sa.String(length=64), nullable=True)
    )
