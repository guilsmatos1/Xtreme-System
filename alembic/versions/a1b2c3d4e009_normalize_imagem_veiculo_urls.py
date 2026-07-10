"""normalize imagem_veiculo urls

Revision ID: a1b2c3d4e009
Revises: a1b2c3d4e008
Create Date: 2026-07-10 15:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e009"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rewrite legacy /media/veiculos URLs to /static/uploads/veiculos."""
    conn = op.get_bind()
    tabela = sa.table(
        "imagem_veiculo",
        sa.column("id", sa.Integer()),
        sa.column("url", sa.String()),
    )
    rows = conn.execute(
        sa.select(tabela.c.id, tabela.c.url).where(
            tabela.c.url.like("/media/veiculos/%")
        )
    ).all()
    for row_id, url in rows:
        novo_url = url.replace("/media/veiculos/", "/static/uploads/veiculos/", 1)
        conn.execute(
            tabela.update().where(tabela.c.id == row_id).values(url=novo_url)
        )


def downgrade() -> None:
    """Restore legacy /media/veiculos URLs."""
    conn = op.get_bind()
    tabela = sa.table(
        "imagem_veiculo",
        sa.column("id", sa.Integer()),
        sa.column("url", sa.String()),
    )
    rows = conn.execute(
        sa.select(tabela.c.id, tabela.c.url).where(
            tabela.c.url.like("/static/uploads/veiculos/%")
        )
    ).all()
    for row_id, url in rows:
        novo_url = url.replace("/static/uploads/veiculos/", "/media/veiculos/", 1)
        conn.execute(
            tabela.update().where(tabela.c.id == row_id).values(url=novo_url)
        )
