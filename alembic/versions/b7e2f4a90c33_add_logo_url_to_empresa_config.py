"""add logo_url to empresa_config

Revision ID: b7e2f4a90c33
Revises: a1c4e7f90b21
Create Date: 2026-07-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2f4a90c33"
down_revision: str | Sequence[str] | None = "a1c4e7f90b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "empresa_config",
        sa.Column("logo_url", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("empresa_config", "logo_url")
