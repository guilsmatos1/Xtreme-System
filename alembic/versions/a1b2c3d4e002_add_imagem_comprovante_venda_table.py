"""add imagem_comprovante_venda table

Revision ID: a1b2c3d4e002
Revises: a1b2c3d4e001
Create Date: 2026-07-09 18:01:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e002"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create imagem_comprovante_venda table."""
    op.create_table(
        "imagem_comprovante_venda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venda_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["venda_id"], ["venda.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_imagem_comprovante_venda_venda_id"),
        "imagem_comprovante_venda",
        ["venda_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop imagem_comprovante_venda table."""
    op.drop_index(
        op.f("ix_imagem_comprovante_venda_venda_id"),
        table_name="imagem_comprovante_venda",
    )
    op.drop_table("imagem_comprovante_venda")
