"""merge auto_migration heads

Revision ID: bc352f2dda69
Revises: 06e6490f892a, e641f2575307
Create Date: 2026-07-20 10:22:30.390434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc352f2dda69'
down_revision: Union[str, Sequence[str], None] = ('06e6490f892a', 'e641f2575307')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
