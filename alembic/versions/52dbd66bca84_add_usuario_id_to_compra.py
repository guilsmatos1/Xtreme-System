"""add usuario_id to compra

Revision ID: 52dbd66bca84
Revises: d0f75a3b3025
Create Date: 2026-07-22 11:52:54.843204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52dbd66bca84'
down_revision: Union[str, Sequence[str], None] = 'd0f75a3b3025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('compra', sa.Column('usuario_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_compra_usuario_id'), 'compra', ['usuario_id'], unique=False)
    op.create_foreign_key(
        'fk_compra_usuario_id_usuario',
        'compra', 'usuario', ['usuario_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_compra_usuario_id_usuario', 'compra', type_='foreignkey', if_exists=True)
    op.drop_index(op.f('ix_compra_usuario_id'), table_name='compra')
    op.drop_column('compra', 'usuario_id')
