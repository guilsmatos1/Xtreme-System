"""add empresa_config table

Revision ID: b7d1e9c4a201
Revises: e641f2575307
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d1e9c4a201'
down_revision: Union[str, Sequence[str], None] = 'e641f2575307'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create empresa_config table."""
    op.create_table(
        'empresa_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('logo_url', sa.String(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Drop empresa_config table."""
    op.drop_table('empresa_config')
