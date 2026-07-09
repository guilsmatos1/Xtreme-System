"""add vendedor_id to venda

Revision ID: 5dc6beff16d0
Revises: d9babf49fd9b
Create Date: 2026-07-09 17:20:24.636146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dc6beff16d0'
down_revision: Union[str, Sequence[str], None] = 'd9babf49fd9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('venda', sa.Column('vendedor_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_venda_vendedor_id'), 'venda', ['vendedor_id'], unique=False)
    op.create_foreign_key(
        'fk_venda_vendedor_id_usuario',
        'venda', 'usuario', ['vendedor_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_venda_vendedor_id_usuario', 'venda', type_='foreignkey')
    op.drop_index(op.f('ix_venda_vendedor_id'), table_name='venda')
    op.drop_column('venda', 'vendedor_id')
