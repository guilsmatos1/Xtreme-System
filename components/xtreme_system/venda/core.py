"""Venda: enum de status, model (com FKs), schemas e CRUD."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import Veiculo, VeiculoRead


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


def create(session: Session, data: VendaCreate) -> Venda:
    return crud.create(session, Venda, data)


def update(session: Session, obj: Venda, data: VendaUpdate) -> Venda:
    return crud.update(session, obj, data)


def delete(session: Session, obj: Venda) -> None:
    crud.delete(session, obj)
