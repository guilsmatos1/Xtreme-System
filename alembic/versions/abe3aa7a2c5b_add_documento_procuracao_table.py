"""add documento_procuracao table

Revision ID: abe3aa7a2c5b
Revises: a9c8d7e6f5b4
Create Date: 2026-07-14 12:56:49.088078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abe3aa7a2c5b'
down_revision: Union[str, Sequence[str], None] = 'a9c8d7e6f5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'documento_procuracao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_documento_procuracao_veiculo_id'), 'documento_procuracao', ['veiculo_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documento_procuracao_veiculo_id'), table_name='documento_procuracao')
    op.drop_table('documento_procuracao')
