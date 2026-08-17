"""add telegram_config table and investidor.notificar_telegram

Revision ID: c3a5b7d19f42
Revises: b2f4a9c17e33
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a5b7d19f42"
down_revision: str | Sequence[str] | None = "b2f4a9c17e33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MENSAGEM_TEMPLATE_PADRAO = (
    "\N{AUTOMOBILE} Venda registrada!\n"
    "Investidor: {investidor}\n"
    "Cliente: {cliente}\n"
    "Veículo: {veiculo}\n"
    "Valor: R$ {valor}\n"
    "Forma de pagamento: {forma_pagamento} ({parcelas}x)\n"
    "Vendedor: {vendedor}"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'telegram_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('bot_token', sa.String(), nullable=False, server_default=''),
        sa.Column('chat_id', sa.String(), nullable=False, server_default=''),
        sa.Column(
            'mensagem_template',
            sa.String(),
            nullable=False,
            server_default=MENSAGEM_TEMPLATE_PADRAO,
        ),
    )
    op.add_column(
        'investidor',
        sa.Column(
            'notificar_telegram',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('investidor', 'notificar_telegram')
    op.drop_table('telegram_config')
