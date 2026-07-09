"""add imagem_veiculo and documento_veiculo tables

Revision ID: 3e65ccbaa06a
Revises: 5dc6beff16d0
Create Date: 2026-07-09 17:30:15.436247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e65ccbaa06a'
down_revision: Union[str, Sequence[str], None] = '5dc6beff16d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'imagem_veiculo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_imagem_veiculo_veiculo_id'), 'imagem_veiculo', ['veiculo_id'], unique=False
    )

    op.create_table(
        'documento_veiculo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_documento_veiculo_veiculo_id'), 'documento_veiculo', ['veiculo_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documento_veiculo_veiculo_id'), table_name='documento_veiculo')
    op.drop_table('documento_veiculo')

    op.drop_index(op.f('ix_imagem_veiculo_veiculo_id'), table_name='imagem_veiculo')
    op.drop_table('imagem_veiculo')
