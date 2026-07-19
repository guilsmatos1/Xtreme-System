"""add rate limit state table

Revision ID: b7c8d9e0f1a2
Revises: 1a8a10be7674
Create Date: 2026-07-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "1a8a10be7674"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_state",
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("hits", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("bucket"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_state")
