"""merge admin seed and rate limit drop

Revision ID: dbd66e962a7f
Revises: 1817e76a927c, ab12cd34ef56
Create Date: 2026-07-21 23:10:15.719272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dbd66e962a7f'
down_revision: Union[str, Sequence[str], None] = ('1817e76a927c', 'ab12cd34ef56')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
