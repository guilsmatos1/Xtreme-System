"""fix_compra_status_enum_fechamento_venda_not_null_auditoria_index

Revision ID: 60358370bf3c
Revises: c49d45f6db41
Create Date: 2026-07-16 20:38:37.730857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60358370bf3c'
down_revision: Union[str, Sequence[str], None] = 'c49d45f6db41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE statuscompra AS ENUM ('pendente', 'finalizado', 'cancelado')")
    op.drop_index(op.f('ix_auditoria_criado_em'), table_name='auditoria')
    op.execute("ALTER TABLE compra ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE compra ALTER COLUMN status TYPE statuscompra USING status::statuscompra")
    op.execute("ALTER TABLE compra ALTER COLUMN status SET DEFAULT 'pendente'::statuscompra")
    op.alter_column('fechamento_venda', 'data_fechamento',
               existing_type=sa.DATE(),
               nullable=False,
               existing_server_default=sa.text('CURRENT_DATE'))
    op.drop_constraint(op.f('fk_venda_vendedor_id_usuario'), 'venda', type_='foreignkey')
    op.create_foreign_key(None, 'venda', 'usuario', ['vendedor_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'venda', type_='foreignkey')
    op.create_foreign_key(op.f('fk_venda_vendedor_id_usuario'), 'venda', 'usuario', ['vendedor_id'], ['id'], ondelete='SET NULL')
    op.alter_column('fechamento_venda', 'data_fechamento',
               existing_type=sa.DATE(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_DATE'))
    op.execute("ALTER TABLE compra ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE compra ALTER COLUMN status TYPE VARCHAR USING status::text")
    op.execute("ALTER TABLE compra ALTER COLUMN status SET DEFAULT 'pendente'")
    op.execute("DROP TYPE IF EXISTS statuscompra")
    op.create_index(op.f('ix_auditoria_criado_em'), 'auditoria', [sa.literal_column('criado_em DESC')], unique=False)
