"""add rsd_config table

Revision ID: f9a0b1c2d3e4
Revises: ebedcc4c5814
Create Date: 2026-08-04 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "ebedcc4c5814"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rsd_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, server_default=""),
        sa.Column("senha", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "base_url",
            sa.String(),
            nullable=False,
            server_default="https://lojas.rsdsistema.com.br",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("rsd_config")
