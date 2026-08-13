"""add second phone to cliente

Revision ID: c0e1f2a3b4c5
Revises: a8019e167ae5
Create Date: 2026-08-13 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "a8019e167ae5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("cliente", sa.Column("telefone2", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("cliente", "telefone2")
