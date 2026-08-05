"""replace comissao_percentual with valor_proprietario on consignacao.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-08-05 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "consignacao",
        sa.Column("valor_proprietario", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.execute(
        """
        UPDATE consignacao
        SET valor_proprietario = GREATEST(
            ROUND(valor_venda * (1 - COALESCE(comissao_percentual, 0) / 100), 2),
            0.01
        )
        """
    )
    op.alter_column("consignacao", "valor_proprietario", nullable=False)
    op.create_check_constraint(
        "ck_consignacao_valor_proprietario_positive",
        "consignacao",
        "valor_proprietario > 0",
    )
    op.drop_constraint("ck_consignacao_comissao_range", "consignacao", type_="check")
    op.drop_column("consignacao", "comissao_percentual")


def downgrade() -> None:
    op.add_column(
        "consignacao",
        sa.Column("comissao_percentual", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.execute(
        """
        UPDATE consignacao
        SET comissao_percentual = CASE
            WHEN valor_venda > 0 THEN
                GREATEST(
                    ROUND((1 - valor_proprietario / valor_venda) * 100, 2),
                    0
                )
            ELSE NULL
        END
        """
    )
    op.create_check_constraint(
        "ck_consignacao_comissao_range",
        "consignacao",
        "comissao_percentual IS NULL OR "
        "(comissao_percentual >= 0 AND comissao_percentual <= 100)",
    )
    op.drop_constraint(
        "ck_consignacao_valor_proprietario_positive", "consignacao", type_="check"
    )
    op.drop_column("consignacao", "valor_proprietario")
