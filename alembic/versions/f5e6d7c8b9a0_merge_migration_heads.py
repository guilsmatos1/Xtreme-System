"""merge migration heads

Revision ID: f5e6d7c8b9a0
Revises: a2b3c4d5e6f7, bc352f2dda69, e5f6a7b8c9d0
Create Date: 2026-07-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5e6d7c8b9a0'
down_revision: Union[str, Sequence[str], None] = ('a2b3c4d5e6f7', 'bc352f2dda69', 'e5f6a7b8c9d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
