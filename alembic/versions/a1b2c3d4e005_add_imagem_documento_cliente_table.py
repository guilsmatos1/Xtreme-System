"""add imagem_documento_cliente table

Revision ID: a1b2c3d4e005
Revises: a1b2c3d4e004
Create Date: 2026-07-09 18:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e005"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create imagem_documento_cliente table."""
    op.create_table(
        "imagem_documento_cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cliente_id"], ["cliente.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_imagem_documento_cliente_cliente_id"),
        "imagem_documento_cliente",
        ["cliente_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop imagem_documento_cliente table."""
    op.drop_index(
        op.f("ix_imagem_documento_cliente_cliente_id"),
        table_name="imagem_documento_cliente",
    )
    op.drop_table("imagem_documento_cliente")
