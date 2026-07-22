"""seed default admin

Revision ID: ab12cd34ef56
Revises: 06e6490f892a, e641f2575307
Create Date: 2026-07-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pwdlib import PasswordHash

# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"
down_revision: str | Sequence[str] | None = ("06e6490f892a", "e641f2575307")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_ADMIN_USERNAME = "admin"
_DEFAULT_ADMIN_PASSWORD = "admin"  # noqa: S105 -- senha inicial solicitada no bootstrap


def _ensure_default_admin(connection: sa.engine.Connection) -> None:
    exists = connection.execute(
        sa.text("SELECT 1 FROM usuario WHERE username = :username"),
        {"username": _DEFAULT_ADMIN_USERNAME},
    ).first()
    if exists is not None:
        return

    senha_hash = PasswordHash.recommended().hash(_DEFAULT_ADMIN_PASSWORD)
    connection.execute(
        sa.text(
            """
            INSERT INTO usuario (username, senha_hash, papel, ativo, perfil_id)
            VALUES (:username, :senha_hash, 'admin', true, NULL)
            """
        ),
        {"username": _DEFAULT_ADMIN_USERNAME, "senha_hash": senha_hash},
    )


def upgrade() -> None:
    """Upgrade schema."""
    _ensure_default_admin(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
