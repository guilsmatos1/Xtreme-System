"""add rsd_consulta table

Revision ID: ecc94753acc7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ecc94753acc7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rsd_consulta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tipo",
            sa.Enum("puxar_dados", "unitaria", name="tipoconsultarsd"),
            nullable=False,
        ),
        sa.Column("placa", sa.String(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("campos_aplicados", sa.JSON(), nullable=True),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        sa.Column("erro", sa.String(), nullable=True),
        sa.Column("dossie_id", sa.Integer(), nullable=True),
        sa.Column("status_dossie", sa.String(), nullable=True),
        sa.Column("duracao_ms", sa.Integer(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculo.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_rsd_consulta_placa"), "rsd_consulta", ["placa"], unique=False
    )
    op.create_index(
        op.f("ix_rsd_consulta_veiculo_id"), "rsd_consulta", ["veiculo_id"], unique=False
    )
    op.create_index(
        op.f("ix_rsd_consulta_usuario_id"), "rsd_consulta", ["usuario_id"], unique=False
    )
    op.create_index(
        op.f("ix_rsd_consulta_dossie_id"), "rsd_consulta", ["dossie_id"], unique=False
    )
    op.create_index(
        "ix_rsd_consulta_placa_criado_em",
        "rsd_consulta",
        ["placa", "criado_em"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rsd_consulta_placa_criado_em", table_name="rsd_consulta")
    op.drop_index(op.f("ix_rsd_consulta_dossie_id"), table_name="rsd_consulta")
    op.drop_index(op.f("ix_rsd_consulta_usuario_id"), table_name="rsd_consulta")
    op.drop_index(op.f("ix_rsd_consulta_veiculo_id"), table_name="rsd_consulta")
    op.drop_index(op.f("ix_rsd_consulta_placa"), table_name="rsd_consulta")
    op.drop_table("rsd_consulta")
    sa.Enum(name="tipoconsultarsd").drop(op.get_bind(), checkfirst=True)
