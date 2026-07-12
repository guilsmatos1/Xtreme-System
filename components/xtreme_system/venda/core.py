"""Venda: enum de status, model (com FKs), schemas e CRUD."""

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import StatusVeiculo, TipoVeiculo, Veiculo, VeiculoRead


class StatusVenda(StrEnum):
    pendente = "pendente"
    aprovado = "aprovado"
    cancelado = "cancelado"
    concluido = "concluido"


class Venda(Base):
    __tablename__ = "venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey("veiculo.id"), index=True)
    vendedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), index=True
    )
    data_venda: Mapped[date] = mapped_column(Date)
    valor_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_entrada: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    forma_pagamento: Mapped[str]
    parcelas: Mapped[int]
    status: Mapped[StatusVenda] = mapped_column(default=StatusVenda.pendente)
    observacoes: Mapped[str | None]

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    veiculo: Mapped[Veiculo] = relationship(lazy="joined")
    vendedor: Mapped[Usuario | None] = relationship(lazy="joined")


class VendaCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    vendedor_id: int | None = None
    data_venda: date | None = None
    valor_venda: Decimal
    valor_entrada: Decimal | None = None
    debitos: Decimal | None = None
    forma_pagamento: str
    parcelas: int
    status: StatusVenda = StatusVenda.pendente
    observacoes: str | None = None


class VendaUpdate(BaseModel):
    cliente_id: int | None = None
    veiculo_id: int | None = None
    vendedor_id: int | None = None
    data_venda: date | None = None
    valor_venda: Decimal | None = None
    valor_entrada: Decimal | None = None
    debitos: Decimal | None = None
    forma_pagamento: str | None = None
    parcelas: int | None = None
    status: StatusVenda | None = None
    observacoes: str | None = None


class VendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente: ClienteRead
    veiculo: VeiculoRead
    vendedor: UsuarioRead | None
    data_venda: date
    valor_venda: Decimal
    valor_entrada: Decimal | None
    debitos: Decimal | None
    forma_pagamento: str
    parcelas: int
    status: StatusVenda
    observacoes: str | None


def list_all(session: Session) -> list[Venda]:
    return crud.list_all(session, Venda)


def get(session: Session, venda_id: int) -> Venda | None:
    return crud.get(session, Venda, venda_id)


def _status_veiculo_para_venda(status: StatusVenda) -> StatusVeiculo | None:
    if status == StatusVenda.concluido:
        return StatusVeiculo.vendido
    if status == StatusVenda.cancelado:
        return StatusVeiculo.disponivel
    return None


def _sincronizar_status_veiculo(
    session: Session,
    obj: Venda,
    *,
    veiculo_anterior_id: int | None = None,
    status_anterior: StatusVenda | None = None,
) -> Venda:
    status_veiculo = _status_veiculo_para_venda(obj.status)
    sincronizado = False
    if (
        veiculo_anterior_id is not None
        and veiculo_anterior_id != obj.veiculo_id
        and status_anterior == StatusVenda.concluido
    ):
        veiculo_anterior = session.get(Veiculo, veiculo_anterior_id)
        if veiculo_anterior is not None:
            veiculo_anterior.status = StatusVeiculo.disponivel
            sincronizado = True
    if status_veiculo is not None:
        obj.veiculo.status = status_veiculo
        sincronizado = True
    if not sincronizado:
        return obj
    session.commit()
    session.refresh(obj)
    return obj


def create(session: Session, data: VendaCreate) -> Venda:
    obj = crud.create(session, Venda, data)
    return _sincronizar_status_veiculo(session, obj)


def update(session: Session, obj: Venda, data: VendaUpdate) -> Venda:
    veiculo_anterior_id = obj.veiculo_id
    status_anterior = obj.status
    obj = crud.update(session, obj, data)
    return _sincronizar_status_veiculo(
        session,
        obj,
        veiculo_anterior_id=veiculo_anterior_id,
        status_anterior=status_anterior,
    )


def delete(session: Session, obj: Venda) -> None:
    crud.delete(session, obj)


def _mes_atual_inicio() -> date:
    hoje = datetime.now(UTC).date()
    return hoje.replace(day=1)


def resumo_mes(session: Session) -> tuple[int, Decimal]:
    """Retorna (contagem, soma) de vendas do mês atual com status != cancelado."""
    resultado = (
        session.query(func.count(Venda.id), func.sum(Venda.valor_venda))
        .filter(Venda.data_venda >= _mes_atual_inicio())
        .filter(Venda.status != StatusVenda.cancelado)
        .all()
    )
    count, total = resultado[0] if resultado else (0, None)
    return count or 0, total or Decimal("0")


def ticket_medio(session: Session) -> Decimal:
    """Retorna valor médio de venda com status != cancelado."""
    valor = (
        session.query(func.avg(Venda.valor_venda))
        .filter(Venda.status != StatusVenda.cancelado)
        .scalar()
    )
    return valor or Decimal("0")


def receita_por_tipo(session: Session) -> dict[TipoVeiculo, Decimal]:
    """Retorna soma de valor_venda agrupada por tipo de veículo, sem cancelados."""
    rows = (
        session.query(Veiculo.tipo, func.sum(Venda.valor_venda))
        .join(Venda, Venda.veiculo_id == Veiculo.id)
        .filter(Venda.status != StatusVenda.cancelado)
        .group_by(Veiculo.tipo)
        .all()
    )
    return {tipo: total or Decimal("0") for tipo, total in rows}


def funil_status(session: Session) -> dict[StatusVenda, tuple[int, Decimal]]:
    """Retorna (contagem, soma) de vendas por status (incluindo cancelado)."""
    rows = (
        session.query(Venda.status, func.count(Venda.id), func.sum(Venda.valor_venda))
        .group_by(Venda.status)
        .all()
    )
    return {
        status: (count or 0, total or Decimal("0")) for status, count, total in rows
    }


def ranking_vendedores(
    session: Session, limite: int = 5
) -> list[tuple[Usuario, int, Decimal]]:
    """Retorna top N vendedores por valor vendido (status != cancelado).

    Retorna: (usuario, count, total_valor)
    """
    rows = (
        session.query(
            Usuario,
            func.count(Venda.id).label("count_vendas"),
            func.sum(Venda.valor_venda).label("total_valor"),
        )
        .join(Venda, Venda.vendedor_id == Usuario.id)
        .filter(Venda.status != StatusVenda.cancelado)
        .group_by(Usuario.id)
        .order_by(func.sum(Venda.valor_venda).desc())
        .limit(limite)
        .all()
    )
    return [
        (usuario, count or 0, total or Decimal("0")) for usuario, count, total in rows
    ]
