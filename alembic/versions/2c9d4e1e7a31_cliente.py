"""cliente

Revision ID: 2c9d4e1e7a31
Revises: 74df76569f91
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c9d4e1e7a31'
down_revision: Union[str, Sequence[str], None] = '74df76569f91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cliente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(), nullable=False),
        sa.Column('documento', sa.String(), nullable=False),
        sa.Column('tipo', sa.Enum('pessoa_fisica', 'pessoa_juridica', name='tipocliente'), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('telefone', sa.String(), nullable=True),
        sa.Column('endereco', sa.String(), nullable=True),
        sa.Column('cidade', sa.String(), nullable=True),
        sa.Column('estado', sa.String(), nullable=True),
        sa.Column('cep', sa.String(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cliente_documento'), 'cliente', ['documento'], unique=True)
    op.create_index(op.f('ix_cliente_nome'), 'cliente', ['nome'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_cliente_nome'), table_name='cliente')
    op.drop_index(op.f('ix_cliente_documento'), table_name='cliente')
    op.drop_table('cliente')
