"""add valor_documento to venda

Revision ID: a7c3e1b9d204
Revises: d4141526a8b2
Create Date: 2026-08-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e1b9d204"
down_revision: str | Sequence[str] | None = "d4141526a8b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add free-text valor_documento field to venda table."""
    op.add_column("venda", sa.Column("valor_documento", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove valor_documento field from venda table."""
    op.drop_column("venda", "valor_documento")
