"""add documento_contrato_venda table

Revision ID: ca0ad54ee2bc
Revises: 11a007556d5f
Create Date: 2026-07-14 16:36:14.602088

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ca0ad54ee2bc"
down_revision: Union[str, Sequence[str], None] = "11a007556d5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'documento_contrato_venda',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('venda_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['venda_id'], ['venda.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_documento_contrato_venda_venda_id'), 'documento_contrato_venda', ['venda_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documento_contrato_venda_venda_id'), table_name='documento_contrato_venda')
    op.drop_table('documento_contrato_venda')
