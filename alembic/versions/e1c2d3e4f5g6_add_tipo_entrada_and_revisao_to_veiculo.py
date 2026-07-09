"""add tipo_entrada and revisao to veiculo table.

Revision ID: e1c2d3e4f5g6
Revises: d9babf49fd9b
Create Date: 2026-07-09 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1c2d3e4f5g6'
down_revision: Union[str, Sequence[str], None] = 'd9babf49fd9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the TipoEntrada enum type
    op.execute("CREATE TYPE tipoentrada AS ENUM ('compra', 'consignacao')")

    # Add columns to veiculo table
    op.add_column(
        'veiculo',
        sa.Column('tipo_entrada', sa.Enum('compra', 'consignacao', name='tipoentrada'), nullable=False, server_default='compra')
    )
    op.add_column(
        'veiculo',
        sa.Column('revisao', sa.Boolean(), nullable=False, server_default=sa.false())
    )

    # Remove the server defaults after adding columns
    op.alter_column('veiculo', 'tipo_entrada', server_default=None)
    op.alter_column('veiculo', 'revisao', server_default=None)


def downgrade() -> None:
    # Remove columns from veiculo table
    op.drop_column('veiculo', 'revisao')
    op.drop_column('veiculo', 'tipo_entrada')

    # Drop the enum type
    op.execute("DROP TYPE tipoentrada")
