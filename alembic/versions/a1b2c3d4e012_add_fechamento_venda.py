"""add fechamento venda

Revision ID: a1b2c3d4e012
Revises: f4e5d6c7b8a9
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e012"
down_revision: Union[str, Sequence[str], None] = "f4e5d6c7b8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE tipolancamento ADD VALUE IF NOT EXISTS 'receita_venda'")
            op.execute(
                "ALTER TYPE tipolancamento ADD VALUE IF NOT EXISTS "
                "'distribuicao_lucro'"
            )
            op.execute(
                "ALTER TYPE origemlancamento ADD VALUE IF NOT EXISTS "
                "'fechamento_venda'"
            )

    op.create_table(
        "fechamento_venda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venda_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("data_fechamento", sa.Date(), server_default=sa.func.current_date()),
        sa.Column("receita", sa.Numeric(12, 2), nullable=False),
        sa.Column("custo_veiculo", sa.Numeric(12, 2), nullable=False),
        sa.Column("custos_operacionais", sa.Numeric(12, 2), nullable=False),
        sa.Column("debitos", sa.Numeric(12, 2), nullable=False),
        sa.Column("lucro_liquido", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["venda_id"], ["venda.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fechamento_venda_usuario_id"),
        "fechamento_venda",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fechamento_venda_venda_id"),
        "fechamento_venda",
        ["venda_id"],
        unique=True,
    )
    op.create_table(
        "participacao_fechamento_venda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fechamento_venda_id", sa.Integer(), nullable=False),
        sa.Column("investidor_id", sa.Integer(), nullable=False),
        sa.Column("percentual", sa.Numeric(5, 2), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["fechamento_venda_id"], ["fechamento_venda.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["investidor_id"], ["investidor.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fechamento_venda_id",
            "investidor_id",
            name="uq_participacao_fechamento_investidor",
        ),
    )
    op.create_index(
        op.f("ix_participacao_fechamento_venda_fechamento_venda_id"),
        "participacao_fechamento_venda",
        ["fechamento_venda_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_participacao_fechamento_venda_investidor_id"),
        "participacao_fechamento_venda",
        ["investidor_id"],
        unique=False,
    )
    op.add_column(
        "lancamento_investimento",
        sa.Column("fechamento_venda_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_lancamento_investimento_fechamento_venda_id"),
        "lancamento_investimento",
        ["fechamento_venda_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_lancamento_investimento_fechamento_venda_id",
        "lancamento_investimento",
        "fechamento_venda",
        ["fechamento_venda_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_lancamento_investimento_fechamento_venda_id",
        "lancamento_investimento",
        type_="foreignkey",
        if_exists=True,
    )
    op.drop_index(
        op.f("ix_lancamento_investimento_fechamento_venda_id"),
        table_name="lancamento_investimento",
    )
    op.drop_column("lancamento_investimento", "fechamento_venda_id")
    op.drop_index(
        op.f("ix_participacao_fechamento_venda_investidor_id"),
        table_name="participacao_fechamento_venda",
    )
    op.drop_index(
        op.f("ix_participacao_fechamento_venda_fechamento_venda_id"),
        table_name="participacao_fechamento_venda",
    )
    op.drop_table("participacao_fechamento_venda")
    op.drop_index(op.f("ix_fechamento_venda_venda_id"), table_name="fechamento_venda")
    op.drop_index(
        op.f("ix_fechamento_venda_usuario_id"), table_name="fechamento_venda"
    )
    op.drop_table("fechamento_venda")
