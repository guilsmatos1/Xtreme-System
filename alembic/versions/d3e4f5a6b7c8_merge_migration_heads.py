"""merge migration heads

Revision ID: d3e4f5a6b7c8
Revises: b2c3d4e5f6a7, c8d9e0f1a2b3
Create Date: 2026-07-21 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Sequence[str] | str | None = ("b2c3d4e5f6a7", "c8d9e0f1a2b3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge migration heads."""
    pass


def downgrade() -> None:
    """Downgrade merge."""
    pass
