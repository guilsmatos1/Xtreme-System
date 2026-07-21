"""make parcelas nullable in venda table

Revision ID: b2c3d4e5f6a7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make parcelas column nullable in venda table."""
    op.alter_column("venda", "parcelas", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Make parcelas column non-nullable in venda table."""
    op.alter_column("venda", "parcelas", existing_type=sa.Integer(), nullable=False)
