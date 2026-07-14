"""rename papel enum value vendedor to funcionario

Revision ID: f8a9b0c1d2e3
Revises: b4c5d6e7f8a9
Create Date: 2026-07-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Renaming the enum label also updates every existing row that referenced it.
    op.execute("ALTER TYPE papel RENAME VALUE 'vendedor' TO 'funcionario'")


def downgrade() -> None:
    op.execute("ALTER TYPE papel RENAME VALUE 'funcionario' TO 'vendedor'")
