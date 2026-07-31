"""enforce one concluded venda per veiculo

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-31 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_venda_veiculo_concluida"
INDEX_PREDICATE = "status = 'concluido'"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                f"CREATE UNIQUE INDEX CONCURRENTLY {INDEX_NAME} "
                f"ON venda (veiculo_id) WHERE {INDEX_PREDICATE}"
            )
        return

    op.create_index(
        INDEX_NAME,
        "venda",
        ["veiculo_id"],
        unique=True,
        sqlite_where=sa.text(INDEX_PREDICATE),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
        return

    op.drop_index(INDEX_NAME, table_name="venda")
