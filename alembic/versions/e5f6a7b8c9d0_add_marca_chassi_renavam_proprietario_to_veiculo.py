"""add marca, chassi, renavam, proprietario_registrado to veiculo

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-20 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('veiculo', sa.Column('marca', sa.String(), nullable=True))
    op.add_column('veiculo', sa.Column('chassi', sa.String(), nullable=True))
    op.add_column('veiculo', sa.Column('renavam', sa.String(), nullable=True))
    op.add_column('veiculo', sa.Column('proprietario_registrado', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('veiculo', 'proprietario_registrado')
    op.drop_column('veiculo', 'renavam')
    op.drop_column('veiculo', 'chassi')
    op.drop_column('veiculo', 'marca')
