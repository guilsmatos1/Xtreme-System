"""add idempotency key to compra

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-07-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("compra", sa.Column("idempotency_key", sa.String(length=64)))
    op.create_index(
        op.f("ix_compra_idempotency_key"),
        "compra",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_compra_idempotency_key"), table_name="compra")
    op.drop_column("compra", "idempotency_key")
