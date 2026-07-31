"""restrict deletion of compra parent records

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-07-31 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("compra_cliente_id_fkey", "compra", type_="foreignkey")
    op.drop_constraint("compra_veiculo_id_fkey", "compra", type_="foreignkey")
    op.create_foreign_key(
        "fk_compra_cliente_id_cliente",
        "compra",
        "cliente",
        ["cliente_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_compra_veiculo_id_veiculo",
        "compra",
        "veiculo",
        ["veiculo_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_compra_cliente_id_cliente", "compra", type_="foreignkey")
    op.drop_constraint("fk_compra_veiculo_id_veiculo", "compra", type_="foreignkey")
    op.create_foreign_key(
        "compra_cliente_id_fkey",
        "compra",
        "cliente",
        ["cliente_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "compra_veiculo_id_fkey",
        "compra",
        "veiculo",
        ["veiculo_id"],
        ["id"],
        ondelete="CASCADE",
    )
