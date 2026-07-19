"""merge rate limit heads

Revision ID: b917a5b76841
Revises: b6c7d8e9f0a1, b7c8d9e0f1a2
Create Date: 2026-07-19 08:22:19.374471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b917a5b76841'
down_revision: Union[str, Sequence[str], None] = ('b6c7d8e9f0a1', 'b7c8d9e0f1a2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
