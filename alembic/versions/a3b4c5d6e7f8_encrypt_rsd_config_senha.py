"""encrypt existing rsd_config.senha values

Revision ID: a3b4c5d6e7f8
Revises: f4a5b6c7d8e9
Create Date: 2026-08-04 15:00:00.000000

"""
import base64
import hashlib
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fernet() -> Fernet:
    secret = os.environ.get("RSD_ENCRYPTION_KEY")
    if not secret:
        raise RuntimeError(
            "RSD_ENCRYPTION_KEY não configurada — necessária para recodificar "
            "components/xtreme_system/rsd/core.py:rsd_config.senha nesta migration."
        )
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def upgrade() -> None:
    """Upgrade schema."""
    rsd_config = sa.table(
        "rsd_config", sa.column("id", sa.Integer()), sa.column("senha", sa.String())
    )
    fernet = _fernet()
    connection = op.get_bind()
    for row in connection.execute(sa.select(rsd_config.c.id, rsd_config.c.senha)):
        if not row.senha:
            continue
        try:
            fernet.decrypt(row.senha.encode("ascii"))
        except (InvalidToken, ValueError):
            # Ainda não está cifrada — recodifica o valor em texto plano.
            cifrada = fernet.encrypt(row.senha.encode("utf-8")).decode("ascii")
            connection.execute(
                rsd_config.update()
                .where(rsd_config.c.id == row.id)
                .values(senha=cifrada)
            )


def downgrade() -> None:
    """Downgrade schema."""
    rsd_config = sa.table(
        "rsd_config", sa.column("id", sa.Integer()), sa.column("senha", sa.String())
    )
    fernet = _fernet()
    connection = op.get_bind()
    for row in connection.execute(sa.select(rsd_config.c.id, rsd_config.c.senha)):
        if not row.senha:
            continue
        try:
            plana = fernet.decrypt(row.senha.encode("ascii")).decode("utf-8")
        except InvalidToken:
            continue
        connection.execute(
            rsd_config.update().where(rsd_config.c.id == row.id).values(senha=plana)
        )
