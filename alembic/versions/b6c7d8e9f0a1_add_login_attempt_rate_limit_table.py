"""add login attempt rate limit table

Revision ID: b6c7d8e9f0a1
Revises: 1a8a10be7674
Create Date: 2026-07-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "1a8a10be7674"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempt_rate_limit",
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("scope", "bucket"),
    )


def downgrade() -> None:
    op.drop_table("login_attempt_rate_limit")
