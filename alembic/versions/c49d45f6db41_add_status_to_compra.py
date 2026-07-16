"""add_status_to_compra

Revision ID: c49d45f6db41
Revises: a1b2c3d4e012
Create Date: 2026-07-16 16:59:34.880961

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c49d45f6db41"
down_revision: str | Sequence[str] | None = "a1b2c3d4e012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add status column to compra table."""
    op.add_column(
        "compra",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pendente",
        ),
    )


def downgrade() -> None:
    """Remove status column from compra table."""
    op.drop_column("compra", "status")
