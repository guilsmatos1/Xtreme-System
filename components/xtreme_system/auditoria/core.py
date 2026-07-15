"""Auditoria: model, snapshot helper e escrita/leitura de registros de auditoria."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.orm import Mapped, Session, class_mapper, mapped_column

from xtreme_system.database.core import Base

AUDIT_SKIP = {"auditoria"}
MASK = {"senha_hash", "evolution_api_key"}
TIPO_ACOES: tuple[str, ...] = ("CREATE", "UPDATE", "DELETE")


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
            # str preserves precision for audit snapshots
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


class AuditoriaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tabela: str
    tipo_acao: str
    registro_id: int | None
    usuario_id: int | None
    dados_antes: dict[str, Any] | None
    dados_depois: dict[str, Any] | None
    criado_em: datetime


def _filtros(
    stmt: Any,
    *,
    usuario_id: int | None,
    tabela: str | None,
    tipo_acao: str | None,
    data_de: date | None,
    data_ate: date | None,
) -> Any:
    if usuario_id is not None:
        stmt = stmt.where(Auditoria.usuario_id == usuario_id)
    if tabela:
        stmt = stmt.where(Auditoria.tabela == tabela)
    if tipo_acao:
        stmt = stmt.where(Auditoria.tipo_acao == tipo_acao)
    if data_de is not None:
        stmt = stmt.where(Auditoria.criado_em >= datetime.combine(data_de, time.min))
    if data_ate is not None:
        # Exclusive upper bound cobre o dia inteiro e usa o índice
        fim = datetime.combine(data_ate, time.min) + timedelta(days=1)
        stmt = stmt.where(Auditoria.criado_em < fim)
    return stmt


def query(
    session: Session,
    *,
    usuario_id: int | None = None,
    tabela: str | None = None,
    tipo_acao: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Auditoria]:
    stmt = select(Auditoria).order_by(Auditoria.criado_em.desc())
    stmt = _filtros(
        stmt,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
    )
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt))


def count(
    session: Session,
    *,
    usuario_id: int | None = None,
    tabela: str | None = None,
    tipo_acao: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
) -> int:
    stmt = select(func.count()).select_from(Auditoria)
    stmt = _filtros(
        stmt,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
    )
    return int(session.scalar(stmt) or 0)


def tabelas(session: Session) -> list[str]:
    stmt = select(Auditoria.tabela).distinct().order_by(Auditoria.tabela)
    return list(session.scalars(stmt))


def get(session: Session, registro_id: int) -> Auditoria | None:
    return session.get(Auditoria, registro_id)
