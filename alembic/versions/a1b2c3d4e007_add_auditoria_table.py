"""add auditoria table

Revision ID: a1b2c3d4e007
Revises: 5dc6beff16d0
Create Date: 2026-07-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e007'
down_revision: Union[str, Sequence[str], None] = '5dc6beff16d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'auditoria',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tabela', sa.String(100), nullable=False),
        sa.Column('tipo_acao', sa.String(20), nullable=False),
        sa.Column('registro_id', sa.Integer(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('dados_antes', sa.JSON(), nullable=True),
        sa.Column('dados_depois', sa.JSON(), nullable=True),
        sa.Column(
            'criado_em',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f('ix_auditoria_tabela'), 'auditoria', ['tabela'])
    op.create_index(op.f('ix_auditoria_registro_id'), 'auditoria', ['registro_id'])
    op.create_index(op.f('ix_auditoria_usuario_id'), 'auditoria', ['usuario_id'])
    op.create_foreign_key(
        'fk_auditoria_usuario_id_usuario',
        'auditoria', 'usuario', ['usuario_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_auditoria_usuario_id_usuario', 'auditoria', type_='foreignkey', if_exists=True)
    op.drop_index(op.f('ix_auditoria_usuario_id'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_registro_id'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_tabela'), table_name='auditoria')
    op.drop_table('auditoria')
