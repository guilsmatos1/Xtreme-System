"""index auditoria.criado_em

Revision ID: e7f8a9b0c1d2
Revises: c4d5e6f7a8b9
Create Date: 2026-07-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DESC atende ORDER BY criado_em DESC da listagem de auditoria.
    op.create_index(
        op.f('ix_auditoria_criado_em'), 'auditoria', [sa.text('criado_em DESC')]
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_auditoria_criado_em'), table_name='auditoria')
