"""add perfil de permissoes table and usuario.perfil_id

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e010
Create Date: 2026-07-10 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEITOR_PAGINAS = '["veiculos", "investidores", "clientes", "vendas"]'


def upgrade() -> None:
    op.create_table(
        'perfil',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(), nullable=False),
        sa.Column('paginas', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_perfil_nome'), 'perfil', ['nome'], unique=True)

    op.add_column('usuario', sa.Column('perfil_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_usuario_perfil_id_perfil', 'usuario', 'perfil', ['perfil_id'], ['id']
    )

    # Seed a default "Leitor" profile matching today's fixed vendedor access,
    # and backfill existing vendedor users so nothing loses access silently.
    op.execute(
        f"INSERT INTO perfil (nome, paginas) VALUES ('Leitor', '{_LEITOR_PAGINAS}')"
    )
    op.execute(
        "UPDATE usuario SET perfil_id = (SELECT id FROM perfil WHERE nome = 'Leitor') "
        "WHERE papel::text = 'vendedor'"
    )


def downgrade() -> None:
    op.drop_constraint('fk_usuario_perfil_id_perfil', 'usuario', type_='foreignkey')
    op.drop_column('usuario', 'perfil_id')
    op.drop_index(op.f('ix_perfil_nome'), table_name='perfil')
    op.drop_table('perfil')
