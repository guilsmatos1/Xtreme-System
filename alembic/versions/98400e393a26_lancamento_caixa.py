"""lancamento caixa

Revision ID: 98400e393a26
Revises: 5c6914b729c6
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98400e393a26'
down_revision: Union[str, Sequence[str], None] = '5c6914b729c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lancamento_caixa',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('investidor_id', sa.Integer(), nullable=False),
    sa.Column('veiculo_id', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.Enum('aporte', 'custo', name='tipolancamento'), nullable=False),
    sa.Column('origem', sa.Enum('manual', 'veiculo', name='origemlancamento'), nullable=False),
    sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('descricao', sa.String(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['investidor_id'], ['investidor.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lancamento_caixa_investidor_id'), 'lancamento_caixa', ['investidor_id'], unique=False)
    op.create_index(op.f('ix_lancamento_caixa_veiculo_id'), 'lancamento_caixa', ['veiculo_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_lancamento_caixa_veiculo_id'), table_name='lancamento_caixa')
    op.drop_index(op.f('ix_lancamento_caixa_investidor_id'), table_name='lancamento_caixa')
    op.drop_table('lancamento_caixa')
