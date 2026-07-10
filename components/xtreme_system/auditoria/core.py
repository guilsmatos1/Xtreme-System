"""Auditoria: model, snapshot helper e escrita de registros de auditoria."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, Session, class_mapper, mapped_column

from xtreme_system.database.core import Base

AUDIT_SKIP = {"auditoria"}
MASK = {"senha_hash"}


class Auditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    tabela: Mapped[str] = mapped_column(String(100), index=True)
    tipo_acao: Mapped[str] = mapped_column(String(20))
    registro_id: Mapped[int | None] = mapped_column(Integer, index=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )
    dados_antes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    dados_depois: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def _snapshot(obj: Any) -> dict[str, Any]:
    """Dict from ORM column values, masking sensitive fields.

    Converts Decimal, datetime, enum values to JSON-serializable types.
    """
    data: dict[str, Any] = {}
    for col in class_mapper(obj.__class__).columns:
        val = getattr(obj, col.key)
        if col.key in MASK:
            val = "***"
        elif isinstance(val, date):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            # ponytail: str preserves precision for audit snapshots
            val = str(val)
        elif hasattr(val, "value"):
            val = val.value
        data[col.key] = val
    return data


def auditar(
    session: Session,
    *,
    tabela: str,
    tipo_acao: str,
    registro_id: int | None = None,
    dados_antes: dict[str, Any] | None = None,
    dados_depois: dict[str, Any] | None = None,
) -> None:
    """Write one audit row. usuario_id comes from session.info."""
    if tabela in AUDIT_SKIP:
        return
    usuario_id = session.info.get("usuario_id")
    row = Auditoria(
        tabela=tabela,
        tipo_acao=tipo_acao,
        registro_id=registro_id,
        usuario_id=usuario_id,
        dados_antes=dados_antes,
        dados_depois=dados_depois,
    )
    session.add(row)
