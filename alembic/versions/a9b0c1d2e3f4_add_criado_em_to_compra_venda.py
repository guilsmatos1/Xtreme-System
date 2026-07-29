"""add criado_em to compra and venda

Revision ID: a9b0c1d2e3f4
Revises: e9f0a1b2c3d4
Create Date: 2026-07-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("compra", sa.Column("criado_em", sa.DateTime(), nullable=True))
    op.add_column("venda", sa.Column("criado_em", sa.DateTime(), nullable=True))

    op.execute(
        "UPDATE compra SET criado_em = CAST(data_compra AS TIMESTAMP) "
        "WHERE criado_em IS NULL"
    )
    op.execute(
        "UPDATE venda SET criado_em = "
        "COALESCE(CAST(data_venda AS TIMESTAMP), CURRENT_TIMESTAMP) "
        "WHERE criado_em IS NULL"
    )

    op.alter_column(
        "compra",
        "criado_em",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.alter_column(
        "venda",
        "criado_em",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    op.drop_column("venda", "criado_em")
    op.drop_column("compra", "criado_em")
