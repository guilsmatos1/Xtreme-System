"""persist RSD credential verification state"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rsd_config",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="saved_unverified",
        ),
    )
    op.add_column("rsd_config", sa.Column("ultimo_teste_em", sa.DateTime(timezone=True)))
    op.add_column("rsd_config", sa.Column("ultimo_teste_erro", sa.Text()))
    op.add_column("rsd_config", sa.Column("ultimo_teste_fingerprint", sa.String(length=64)))


def downgrade() -> None:
    op.drop_column("rsd_config", "ultimo_teste_fingerprint")
    op.drop_column("rsd_config", "ultimo_teste_erro")
    op.drop_column("rsd_config", "ultimo_teste_em")
    op.drop_column("rsd_config", "status")
