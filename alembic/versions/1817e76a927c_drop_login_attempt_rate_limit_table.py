"""drop login attempt rate limit table

Revision ID: 1817e76a927c
Revises: d3e4f5a6b7c8
Create Date: 2026-07-21 15:04:15.937477

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1817e76a927c"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("login_attempt_rate_limit")


def downgrade() -> None:
    op.create_table(
        "login_attempt_rate_limit",
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("scope", "bucket"),
    )
