"""add debitos to venda

Revision ID: a1b2c3d4e004
Revises: a1b2c3d4e003
Create Date: 2026-07-09 18:03:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e004"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add debitos column to venda table."""
    op.add_column(
        "venda",
        sa.Column(
            "debitos", sa.Numeric(precision=12, scale=2), nullable=True
        ),
    )


def downgrade() -> None:
    """Remove debitos column from venda table."""
    op.drop_column("venda", "debitos")
