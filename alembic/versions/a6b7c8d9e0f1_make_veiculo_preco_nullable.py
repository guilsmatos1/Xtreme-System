"""make vehicle advertised price nullable

Revision ID: a6b7c8d9e0f1
Revises: f6a7b8c9d0e1
Create Date: 2026-08-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "veiculo",
        "preco",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "veiculo",
        "preco",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
