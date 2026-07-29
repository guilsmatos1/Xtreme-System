"""update vehicle and purchase statuses

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-07-29 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE statusveiculo ADD VALUE IF NOT EXISTS 'indisponivel'")
    op.execute("ALTER TYPE statusveiculo ADD VALUE IF NOT EXISTS 'cancelado'")
    op.execute("ALTER TYPE statuscompra RENAME VALUE 'finalizado' TO 'concluido'")


def downgrade() -> None:
    op.execute("ALTER TYPE statuscompra RENAME VALUE 'concluido' TO 'finalizado'")
