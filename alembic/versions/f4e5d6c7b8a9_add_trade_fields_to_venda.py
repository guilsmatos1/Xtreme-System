"""add trade fields to venda

Revision ID: f4e5d6c7b8a9
Revises: a1b2c3d4e011
Create Date: 2026-07-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4e5d6c7b8a9"
down_revision: str | Sequence[str] | None = "a1b2c3d4e011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add trade and pending payment fields to venda table."""
    op.add_column("venda", sa.Column("veiculo_troca_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_venda_veiculo_troca_id_veiculo",
        "venda",
        "veiculo",
        ["veiculo_troca_id"],
        ["id"],
    )
    op.create_index(
        "ix_venda_veiculo_troca_id",
        "venda",
        ["veiculo_troca_id"],
        unique=False,
    )
    op.add_column(
        "venda", sa.Column("valor_diferenca", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "venda",
        sa.Column(
            "pagamento_pendente",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "venda", sa.Column("valor_pendente", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column("venda", sa.Column("datas_pagamento", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove trade and pending payment fields from venda table."""
    op.drop_column("venda", "datas_pagamento")
    op.drop_column("venda", "valor_pendente")
    op.drop_column("venda", "pagamento_pendente")
    op.drop_column("venda", "valor_diferenca")
    op.drop_index("ix_venda_veiculo_troca_id", table_name="venda")
    op.drop_constraint("fk_venda_veiculo_troca_id_veiculo", "venda", type_="foreignkey")
    op.drop_column("venda", "veiculo_troca_id")
