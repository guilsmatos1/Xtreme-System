"""remove meio_captacao_id from veiculo and drop meio_captacao table.

Revision ID: f2a3b4c5d6e7
Revises: e1c2d3e4f5g6
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_veiculo_meio_captacao_id'), table_name='veiculo')
    op.drop_column('veiculo', 'meio_captacao_id')
    op.drop_index(op.f('ix_meio_captacao_nome'), table_name='meio_captacao')
    op.drop_table('meio_captacao')


def downgrade() -> None:
    op.create_table(
        'meio_captacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_meio_captacao_nome'), 'meio_captacao', ['nome'], unique=True)
    op.add_column(
        'veiculo',
        sa.Column('meio_captacao_id', sa.Integer(), nullable=True),
    )
    op.create_index(op.f('ix_veiculo_meio_captacao_id'), 'veiculo', ['meio_captacao_id'], unique=False)
    op.create_foreign_key(
        None, 'veiculo', 'meio_captacao', ['meio_captacao_id'], ['id'], ondelete='RESTRICT'
    )
