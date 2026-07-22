"""add cep and telefone to empresa_config

Revision ID: a1c4e7f90b21
Revises: 52dbd66bca84
Create Date: 2026-07-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e7f90b21"
down_revision: str | Sequence[str] | None = "52dbd66bca84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "empresa_config",
        sa.Column("cep", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "empresa_config",
        sa.Column("telefone", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("empresa_config", "telefone")
    op.drop_column("empresa_config", "cep")
