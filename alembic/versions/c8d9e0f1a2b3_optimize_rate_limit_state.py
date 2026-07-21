"""optimize rate limit state

Revision ID: c8d9e0f1a2b3
Revises: e641f2575307
Create Date: 2026-07-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "e641f2575307"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("rate_limit_state")
    op.create_table(
        "rate_limit_state",
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("window_started_at", sa.Float(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("bucket"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_state")
    op.create_table(
        "rate_limit_state",
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("hits", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("bucket"),
    )
