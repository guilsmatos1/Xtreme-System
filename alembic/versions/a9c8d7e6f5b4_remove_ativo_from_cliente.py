"""remove ativo from cliente

Revision ID: a9c8d7e6f5b4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-14 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9c8d7e6f5b4"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("cliente", "ativo")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "cliente",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("cliente", "ativo", server_default=None)
