"""add vendedor role, reservado status, and optional data_venda.

Revision ID: d9babf49fd9b
Revises: d9babf49fd9a
Create Date: 2026-07-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9babf49fd9b'
down_revision: Union[str, Sequence[str], None] = 'd9babf49fd9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'vendedor' to papel enum
    op.execute("ALTER TYPE papel ADD VALUE 'vendedor'")

    # Add 'reservado' to statusveiculo enum
    op.execute("ALTER TYPE statusveiculo ADD VALUE 'reservado'")

    # Make data_venda nullable in venda table
    op.alter_column(
        'venda',
        'data_venda',
        existing_type=sa.Date(),
        nullable=True
    )


def downgrade() -> None:
    # Revert data_venda to not nullable
    op.alter_column(
        'venda',
        'data_venda',
        existing_type=sa.Date(),
        nullable=False
    )

    # Note: PostgreSQL doesn't support removing enum values directly.
    # To fully revert enum changes, you would need to:
    # 1. Create new enum types without the new values
    # 2. Cast all column values to the new type
    # 3. Drop the old enum types
    # This is complex and usually not needed in practice.
