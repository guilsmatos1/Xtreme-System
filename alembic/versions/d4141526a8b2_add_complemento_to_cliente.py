"""add complemento to cliente

Revision ID: d4141526a8b2
Revises: d313093e57c1
Create Date: 2026-08-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4141526a8b2"
down_revision: str | Sequence[str] | None = "d313093e57c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("cliente", sa.Column("complemento", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("cliente", "complemento")
