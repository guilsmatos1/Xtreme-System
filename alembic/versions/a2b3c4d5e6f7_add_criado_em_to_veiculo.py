"""add criado_em to veiculo

Revision ID: a2b3c4d5e6f7
Revises: 06e6490f892a, e641f2575307
Create Date: 2026-07-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = ("06e6490f892a", "e641f2575307")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "veiculo",
        sa.Column(
            "criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("veiculo", "criado_em")
