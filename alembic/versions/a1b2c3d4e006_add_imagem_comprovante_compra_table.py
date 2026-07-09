"""add imagem_comprovante_compra table

Revision ID: a1b2c3d4e006
Revises: a1b2c3d4e005
Create Date: 2026-07-09 18:06:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e006"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create imagem_comprovante_compra table."""
    op.create_table(
        "imagem_comprovante_compra",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("compra_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["compra_id"], ["compra.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_imagem_comprovante_compra_compra_id"),
        "imagem_comprovante_compra",
        ["compra_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop imagem_comprovante_compra table."""
    op.drop_index(
        op.f("ix_imagem_comprovante_compra_compra_id"),
        table_name="imagem_comprovante_compra",
    )
    op.drop_table("imagem_comprovante_compra")
