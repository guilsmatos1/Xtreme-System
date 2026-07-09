"""add vendedor role, reservado status, and optional data_venda.

Revision ID: d9babf49fd9b
Revises: d9babf49fd9a
Create Date: 2026-07-09 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d9babf49fd9b"
down_revision = "d9babf49fd9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update usuario.papel enum type to include 'vendedor'
    # PostgreSQL: alter enum type
    op.execute("ALTER TYPE papel ADD VALUE 'vendedor'")

    # Update default papel from 'leitor' to 'vendedor'
    op.alter_column(
        "usuario",
        "papel",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="vendedor",
    )

    # Update statusveiculo enum type to include 'reservado'
    # PostgreSQL: alter enum type
    op.execute("ALTER TYPE statusveiculo ADD VALUE 'reservado'")

    # Make data_venda nullable in venda table
    op.alter_column(
        "venda",
        "data_venda",
        existing_type=sa.Date(),
        existing_nullable=False,
        nullable=True,
    )


def downgrade() -> None:
    # Make data_venda non-nullable again
    op.alter_column(
        "venda",
        "data_venda",
        existing_type=sa.Date(),
        existing_nullable=True,
        nullable=False,
    )

    # Note: PostgreSQL doesn't support removing enum values easily.
    # For a complete downgrade, we'd need to recreate the types,
    # but for now we leave them as is.
    # To fully revert, you'd need to:
    # 1. Create new types without the new values
    # 2. Update all references
    # 3. Drop old types

    # Revert default papel back to 'leitor'
    op.alter_column(
        "usuario",
        "papel",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="leitor",
    )
