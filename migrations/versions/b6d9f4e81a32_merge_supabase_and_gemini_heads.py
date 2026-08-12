"""Supabase 운영 DB 계보와 Gemini TTS 계보를 병합한다.

Revision ID: b6d9f4e81a32
Revises: a1c4e8f52b70, f8b3c9d2a410
Create Date: 2026-08-12
"""

from typing import Sequence, Union

revision: str = "b6d9f4e81a32"
down_revision: Union[str, Sequence[str], None] = (
    "a1c4e8f52b70",
    "f8b3c9d2a410",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """두 분기의 변경은 각 부모 리비전에서 완료된다."""


def downgrade() -> None:
    """병합 지점만 제거하고 두 부모 head로 되돌린다."""
