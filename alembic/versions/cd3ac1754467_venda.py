"""venda

Revision ID: cd3ac1754467
Revises: 2c9d4e1e7a31
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd3ac1754467'
down_revision: Union[str, Sequence[str], None] = '2c9d4e1e7a31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'venda',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), nullable=False),
        sa.Column('data_venda', sa.Date(), nullable=False),
        sa.Column('valor_venda', sa.Numeric(12, 2), nullable=False),
        sa.Column('valor_entrada', sa.Numeric(12, 2), nullable=True),
        sa.Column('forma_pagamento', sa.String(), nullable=False),
        sa.Column('parcelas', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pendente', 'aprovado', 'cancelado', 'concluido', name='statusvenda'), nullable=False),
        sa.Column('observacoes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_venda_cliente_id'), 'venda', ['cliente_id'], unique=False)
    op.create_index(op.f('ix_venda_veiculo_id'), 'venda', ['veiculo_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_venda_veiculo_id'), table_name='venda')
    op.drop_index(op.f('ix_venda_cliente_id'), table_name='venda')
    op.drop_table('venda')
