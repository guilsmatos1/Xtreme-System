"""add proprietario_documento and proprietario_uf to veiculo

Revision ID: f4a5b6c7d8e9
Revises: ecc94753acc7
Create Date: 2026-08-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "ecc94753acc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("veiculo", sa.Column("proprietario_documento", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("proprietario_uf", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("veiculo", "proprietario_uf")
    op.drop_column("veiculo", "proprietario_documento")
