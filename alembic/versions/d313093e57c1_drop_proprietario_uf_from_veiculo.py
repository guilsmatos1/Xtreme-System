"""drop proprietario_uf from veiculo

Revision ID: d313093e57c1
Revises: c0e1f2a3b4c5
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d313093e57c1"
down_revision: Union[str, Sequence[str], None] = "c0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("veiculo", "proprietario_uf")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("veiculo", sa.Column("proprietario_uf", sa.String(), nullable=True))
