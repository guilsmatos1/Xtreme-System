"""add mensagem_template to whatsapp_config

Revision ID: b4c5d6e7f8a9
Revises: e7f8a9b0c1d2
Create Date: 2026-07-12 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MENSAGEM_TEMPLATE_PADRAO = (
    "🚗 Nova venda registrada!\n"
    "Cliente: {cliente}\n"
    "Veículo: {veiculo}\n"
    "Valor: R$ {valor}\n"
    "Forma de pagamento: {forma_pagamento} ({parcelas}x)\n"
    "Vendedor: {vendedor}"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'whatsapp_config',
        sa.Column(
            'mensagem_template',
            sa.String(),
            nullable=False,
            server_default=MENSAGEM_TEMPLATE_PADRAO,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whatsapp_config', 'mensagem_template')
