"""seed investidor Consignado and assign consignacao vehicles.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-08-05 19:37:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INVESTIDOR_CONSIGNADO = "Consignado"


def _investidor_consignado_id(connection: sa.engine.Connection) -> int:
    row = connection.execute(
        sa.text(
            "SELECT id FROM investidor WHERE lower(trim(nome)) = lower(:nome) LIMIT 1"
        ),
        {"nome": _INVESTIDOR_CONSIGNADO},
    ).first()
    if row is not None:
        return int(row[0])

    connection.execute(
        sa.text("INSERT INTO investidor (nome) VALUES (:nome)"),
        {"nome": _INVESTIDOR_CONSIGNADO},
    )
    created = connection.execute(
        sa.text(
            "SELECT id FROM investidor WHERE lower(trim(nome)) = lower(:nome) LIMIT 1"
        ),
        {"nome": _INVESTIDOR_CONSIGNADO},
    ).first()
    assert created is not None  # noqa: S101
    return int(created[0])


def upgrade() -> None:
    connection = op.get_bind()
    consignado_id = _investidor_consignado_id(connection)
    connection.execute(
        sa.text(
            """
            UPDATE veiculo
            SET investidor_id = :investidor_id
            WHERE tipo_entrada = 'consignacao'
            """
        ),
        {"investidor_id": consignado_id},
    )


def downgrade() -> None:
    """Downgrade schema."""
