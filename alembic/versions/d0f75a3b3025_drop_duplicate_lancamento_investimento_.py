"""drop duplicate lancamento_investimento investidor fkey

Revision ID: d0f75a3b3025
Revises: dbd66e962a7f
Create Date: 2026-07-22 10:56:14.076166

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0f75a3b3025'
down_revision: Union[str, Sequence[str], None] = 'dbd66e962a7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 06e6490f892a and e641f2575307 are duplicate auto-generated migrations on
    # parallel branches that both got merged into head; each ran an unnamed
    # create_foreign_key for lancamento_investimento.investidor_id, so Postgres
    # silently created a second constraint with a "1" suffix instead of erroring.
    op.drop_constraint(
        "lancamento_investimento_investidor_id_fkey1",
        "lancamento_investimento",
        type_="foreignkey",
        if_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.create_foreign_key(
        "lancamento_investimento_investidor_id_fkey1",
        "lancamento_investimento",
        "investidor",
        ["investidor_id"],
        ["id"],
    )
