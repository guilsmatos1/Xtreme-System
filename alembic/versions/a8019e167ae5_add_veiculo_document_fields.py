"""add document fields to veiculo and rename proprietario_registrado to proprietario_atual

Revision ID: a8019e167ae5
Revises: f3a4b5c6d7e8
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8019e167ae5"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("veiculo", sa.Column("numero_motor", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("combustivel", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("tipo_documento", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("categoria", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("especie", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("procedencia", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("municipio", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("potencia", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("cilindrada", sa.String(), nullable=True))
    op.add_column(
        "veiculo", sa.Column("proprietario_anterior", sa.String(), nullable=True)
    )
    op.alter_column(
        "veiculo", "proprietario_registrado", new_column_name="proprietario_atual"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "veiculo", "proprietario_atual", new_column_name="proprietario_registrado"
    )
    op.drop_column("veiculo", "proprietario_anterior")
    op.drop_column("veiculo", "cilindrada")
    op.drop_column("veiculo", "potencia")
    op.drop_column("veiculo", "municipio")
    op.drop_column("veiculo", "procedencia")
    op.drop_column("veiculo", "especie")
    op.drop_column("veiculo", "categoria")
    op.drop_column("veiculo", "tipo_documento")
    op.drop_column("veiculo", "combustivel")
    op.drop_column("veiculo", "numero_motor")
