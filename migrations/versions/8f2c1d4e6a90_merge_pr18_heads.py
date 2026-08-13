"""merge PR 18 migration heads

Revision ID: 8f2c1d4e6a90
Revises: f4a8d1e62c93, 3a5d8c1e7f20
"""

from typing import Sequence, Union

revision: str = "8f2c1d4e6a90"
down_revision: Union[str, Sequence[str], None] = (
    "f4a8d1e62c93",
    "3a5d8c1e7f20",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """두 부모 revision의 변경은 각 계보에서 완료된다."""


def downgrade() -> None:
    """병합 지점만 제거하고 두 부모 head로 되돌린다."""
