"""index fechamento_venda.data_fechamento

Revision ID: d8e9f0a1b2c3
Revises: b7e2f4a90c33
Create Date: 2026-07-25 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "b7e2f4a90c33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_fechamento_venda_data_fechamento"),
        "fechamento_venda",
        ["data_fechamento"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_fechamento_venda_data_fechamento"),
        table_name="fechamento_venda",
    )
