"""add restricoes to perfil

Revision ID: 1a8a10be7674
Revises: 60358370bf3c
Create Date: 2026-07-17 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1a8a10be7674'
down_revision: Union[str, Sequence[str], None] = '60358370bf3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "perfil",
        sa.Column(
            "restricoes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
    )


def downgrade() -> None:
    op.drop_column("perfil", "restricoes")
