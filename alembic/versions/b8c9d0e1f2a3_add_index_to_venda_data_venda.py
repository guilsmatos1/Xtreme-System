"""add index to venda data_venda

Revision ID: b8c9d0e1f2a3
Revises: a6b7c8d9e0f1
Create Date: 2026-08-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_venda_data_venda"),
        "venda",
        ["data_venda"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_venda_data_venda"), table_name="venda")
