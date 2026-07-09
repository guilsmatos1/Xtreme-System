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
    # Note: PostgreSQL doesn't support removing enum values directly.
    # Downgrading enum additions is not safely reversible without dropping and
    # recreating the entire type and dependent columns. This migration is one-way.
    # If rollback is needed, manually drop the database and restore from backup.

    # Only revert data_venda to not nullable if no NULL values exist
    # (This may fail if NULL values were inserted)
    op.alter_column(
        'venda',
        'data_venda',
        existing_type=sa.Date(),
        nullable=False
    )
