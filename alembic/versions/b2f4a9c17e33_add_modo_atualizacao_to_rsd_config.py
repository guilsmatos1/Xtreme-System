"""add modo_atualizacao to rsd_config

Revision ID: b2f4a9c17e33
Revises: a7c3e1b9d204
Create Date: 2026-08-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f4a9c17e33"
down_revision: str | Sequence[str] | None = "a7c3e1b9d204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add modo_atualizacao (atpv/crlv) to rsd_config, default crlv."""
    op.add_column(
        "rsd_config",
        sa.Column(
            "modo_atualizacao",
            sa.String(),
            nullable=False,
            server_default="crlv",
        ),
    )


def downgrade() -> None:
    """Remove modo_atualizacao from rsd_config."""
    op.drop_column("rsd_config", "modo_atualizacao")
