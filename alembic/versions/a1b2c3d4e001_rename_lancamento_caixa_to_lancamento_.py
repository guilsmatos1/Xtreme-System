"""rename lancamento_caixa to lancamento_investimento

Revision ID: a1b2c3d4e001
Revises: 3e65ccbaa06a
Create Date: 2026-07-09 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e001"
down_revision: Union[str, Sequence[str], None] = "3e65ccbaa06a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename lancamento_caixa table and indexes to lancamento_investimento."""
    # Rename indexes first
    op.execute(
        "ALTER INDEX ix_lancamento_caixa_investidor_id "
        "RENAME TO ix_lancamento_investimento_investidor_id"
    )
    op.execute(
        "ALTER INDEX ix_lancamento_caixa_veiculo_id "
        "RENAME TO ix_lancamento_investimento_veiculo_id"
    )
    # Rename primary key
    op.execute(
        "ALTER INDEX lancamento_caixa_pkey "
        "RENAME TO lancamento_investimento_pkey"
    )
    # Rename the table
    op.rename_table("lancamento_caixa", "lancamento_investimento")
    # Make veiculo_id unique to match the SQLAlchemy model
    op.drop_index(
        op.f("ix_lancamento_investimento_veiculo_id"),
        table_name="lancamento_investimento",
    )
    op.create_index(
        op.f("ix_lancamento_investimento_veiculo_id"),
        "lancamento_investimento",
        ["veiculo_id"],
        unique=True,
    )


def downgrade() -> None:
    """Revert renaming."""
    op.drop_index(
        op.f("ix_lancamento_investimento_veiculo_id"),
        table_name="lancamento_investimento",
    )
    op.create_index(
        op.f("ix_lancamento_investimento_veiculo_id"),
        "lancamento_investimento",
        ["veiculo_id"],
        unique=False,
    )
    op.rename_table("lancamento_investimento", "lancamento_caixa")
    op.execute(
        "ALTER INDEX lancamento_investimento_pkey "
        "RENAME TO lancamento_caixa_pkey"
    )
    op.execute(
        "ALTER INDEX ix_lancamento_investimento_veiculo_id "
        "RENAME TO ix_lancamento_caixa_veiculo_id"
    )
    op.execute(
        "ALTER INDEX ix_lancamento_investimento_investidor_id "
        "RENAME TO ix_lancamento_caixa_investidor_id"
    )
