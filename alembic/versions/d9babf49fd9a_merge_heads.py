"""merge heads

Revision ID: d9babf49fd9a
Revises: 98400e393a26, cd3ac1754467
Create Date: 2026-07-09 16:50:15.561451

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9babf49fd9a'
down_revision: Union[str, Sequence[str], None] = ('98400e393a26', 'cd3ac1754467')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
