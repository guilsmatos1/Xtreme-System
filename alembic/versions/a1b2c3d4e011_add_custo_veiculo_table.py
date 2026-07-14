"""add custo_veiculo table

Revision ID: a1b2c3d4e011
Revises: ca0ad54ee2bc
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e011"
down_revision: str | Sequence[str] | None = "ca0ad54ee2bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custo_veiculo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=True),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("data_custo", sa.Date(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_custo_veiculo_veiculo_id"),
        "custo_veiculo",
        ["veiculo_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_custo_veiculo_veiculo_id"), table_name="custo_veiculo")
    op.drop_table("custo_veiculo")
