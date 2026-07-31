"""add database checks for money invariants

Revision ID: f6a7b8c9d0e1
Revises: c2d3e4f5a6b7
Create Date: 2026-07-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONSTRAINTS: dict[str, tuple[tuple[str, str], ...]] = {
    "veiculo": (("ck_veiculo_preco_positive", "preco > 0"),),
    "venda": (
        ("ck_venda_valor_venda_positive", "valor_venda > 0"),
        (
            "ck_venda_valor_entrada_nonnegative",
            "valor_entrada IS NULL OR valor_entrada >= 0",
        ),
        (
            "ck_venda_valor_entrada_lte_valor_venda",
            "valor_entrada IS NULL OR valor_entrada <= valor_venda",
        ),
        ("ck_venda_debitos_nonnegative", "debitos IS NULL OR debitos >= 0"),
        (
            "ck_venda_valor_diferenca_nonnegative",
            "valor_diferenca IS NULL OR valor_diferenca >= 0",
        ),
        (
            "ck_venda_valor_pendente_nonnegative",
            "valor_pendente IS NULL OR valor_pendente >= 0",
        ),
    ),
    "compra": (
        ("ck_compra_valor_compra_positive", "valor_compra > 0"),
        ("ck_compra_debitos_nonnegative", "debitos IS NULL OR debitos >= 0"),
    ),
    "custo_veiculo": (("ck_custo_veiculo_valor_positive", "valor > 0"),),
    "lancamento_investimento": (
        (
            "ck_lancamento_investimento_valor_positive",
            "valor > 0 OR (origem = 'veiculo' AND valor = 0)",
        ),
    ),
    "participacao_fechamento_venda": (
        (
            "ck_participacao_percentual_range",
            "percentual > 0 AND percentual <= 100",
        ),
    ),
}


def _add_postgresql_constraint(table: str, name: str, condition: str) -> None:
    op.execute(
        sa.text(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
            f"CHECK ({condition}) NOT VALID"
        )
    )
    op.execute(
        sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"')
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table, constraints in _CONSTRAINTS.items():
            for name, condition in constraints:
                _add_postgresql_constraint(table, name, condition)
        return

    for table, constraints in _CONSTRAINTS.items():
        with op.batch_alter_table(table, recreate="always") as batch_op:
            for name, condition in constraints:
                batch_op.create_check_constraint(name, condition)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table, constraints in _CONSTRAINTS.items():
            for name, _condition in reversed(constraints):
                op.drop_constraint(name, table, type_="check")
        return

    for table, constraints in _CONSTRAINTS.items():
        with op.batch_alter_table(table, recreate="always") as batch_op:
            for name, _condition in reversed(constraints):
                batch_op.drop_constraint(name, type_="check")
