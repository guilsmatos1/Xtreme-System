"""add compra table

Revision ID: a1b2c3d4e003
Revises: a1b2c3d4e002
Create Date: 2026-07-09 18:02:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e003"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create compra table."""
    op.create_table(
        "compra",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("data_compra", sa.Date(), nullable=False),
        sa.Column("valor_compra", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("debitos", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("observacoes", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cliente_id"], ["cliente.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["veiculo_id"], ["veiculo.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_compra_cliente_id"), "compra", ["cliente_id"], unique=False
    )
    op.create_index(
        op.f("ix_compra_veiculo_id"), "compra", ["veiculo_id"], unique=False
    )


def downgrade() -> None:
    """Drop compra table."""
    op.drop_index(op.f("ix_compra_veiculo_id"), table_name="compra")
    op.drop_index(op.f("ix_compra_cliente_id"), table_name="compra")
    op.drop_table("compra")
