"""add km to venda

Revision ID: 11a007556d5f
Revises: abe3aa7a2c5b
Create Date: 2026-07-14 16:36:14.602088

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "11a007556d5f"
down_revision: Union[str, Sequence[str], None] = "abe3aa7a2c5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add km column to venda table."""
    op.add_column(
        "venda",
        sa.Column("km", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove km column from venda table."""
    op.drop_column("venda", "km")
