"""merge token_version and rsd/consignacao heads

Revision ID: a1b2c3d4e5f6
Revises: c9d0e1f2a3b4, f9a0b1c2d3e4
Create Date: 2026-08-04 09:55:00.000000

"""

from collections.abc import Sequence

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = ("c9d0e1f2a3b4", "f9a0b1c2d3e4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
