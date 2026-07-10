"""add whatsapp_config table

Revision ID: a1b2c3d4e008
Revises: a1b2c3d4e007
Create Date: 2026-07-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e008'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'whatsapp_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('evolution_api_url', sa.String(), nullable=False, server_default=''),
        sa.Column('evolution_api_key', sa.String(), nullable=False, server_default=''),
        sa.Column('evolution_instance', sa.String(), nullable=False, server_default=''),
        sa.Column('evolution_group_id', sa.String(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('whatsapp_config')
