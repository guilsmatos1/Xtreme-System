"""Compra: model (com FKs para cliente e veiculo), schemas e CRUD."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.veiculo.core import Veiculo, VeiculoRead


class Compra(Base):
    __tablename__ = "compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.id", ondelete="CASCADE"), index=True
    )
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    data_compra: Mapped[date] = mapped_column(Date)
    valor_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    observacoes: Mapped[str | None]

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    veiculo: Mapped[Veiculo] = relationship(lazy="joined")


class CompraCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    data_compra: date | None = None
    valor_compra: Decimal
    debitos: Decimal | None = None
    observacoes: str | None = None


class CompraUpdate(BaseModel):
    cliente_id: int | None = None
    veiculo_id: int | None = None
    data_compra: date | None = None
    valor_compra: Decimal | None = None
    debitos: Decimal | None = None
    observacoes: str | None = None


class CompraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente: ClienteRead
    veiculo: VeiculoRead
    data_compra: date
    valor_compra: Decimal
    debitos: Decimal | None
    observacoes: str | None


def list_all(session: Session) -> list[Compra]:
    return crud.list_all(session, Compra)


def get_latest_by_veiculo(session: Session, veiculo_id: int) -> Compra | None:
    return (
        session.query(Compra)
        .filter_by(veiculo_id=veiculo_id)
        .order_by(Compra.data_compra.desc(), Compra.id.desc())
        .first()
    )


def latest_by_veiculo_ids(
    session: Session, veiculo_ids: list[int]
) -> dict[int, Compra]:
    if not veiculo_ids:
        return {}
    compras = (
        session.query(Compra)
        .filter(Compra.veiculo_id.in_(veiculo_ids))
        .order_by(Compra.veiculo_id, Compra.data_compra.desc(), Compra.id.desc())
        .all()
    )
    latest: dict[int, Compra] = {}
    for item in compras:
        latest.setdefault(item.veiculo_id, item)
    return latest


def get(session: Session, compra_id: int) -> Compra | None:
    return crud.get(session, Compra, compra_id)


def create(session: Session, data: CompraCreate) -> Compra:
    return crud.create(session, Compra, data)


def update(session: Session, obj: Compra, data: CompraUpdate) -> Compra:
    return crud.update(session, obj, data)


def delete(session: Session, obj: Compra) -> None:
    crud.delete(session, obj)
