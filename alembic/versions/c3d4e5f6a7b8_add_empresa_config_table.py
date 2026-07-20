"""add empresa_config table

Revision ID: c3d4e5f6a7b8
Revises: 41da3737f3bd
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = '41da3737f3bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'empresa_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(), nullable=False, server_default=''),
        sa.Column('endereco', sa.String(), nullable=False, server_default=''),
        sa.Column('bairro', sa.String(), nullable=False, server_default=''),
        sa.Column('cidade', sa.String(), nullable=False, server_default=''),
        sa.Column('uf', sa.String(), nullable=False, server_default=''),
        sa.Column('cnpj', sa.String(), nullable=False, server_default=''),
        sa.Column('signatario', sa.String(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('empresa_config')
