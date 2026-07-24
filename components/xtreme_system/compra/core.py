"""Compra: model (com FKs para cliente e veiculo), schemas e CRUD."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, ForeignKey, Numeric, String, cast, or_
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import Veiculo, VeiculoRead


class StatusCompra(StrEnum):
    pendente = "pendente"
    finalizado = "finalizado"
    cancelado = "cancelado"


class Compra(Base):
    __tablename__ = "compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.id", ondelete="CASCADE"), index=True
    )
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )
    data_compra: Mapped[date] = mapped_column(Date)
    valor_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    observacoes: Mapped[str | None]
    status: Mapped[StatusCompra] = mapped_column(default=StatusCompra.pendente)

    cliente: Mapped[Cliente] = relationship(lazy="selectin")
    veiculo: Mapped[Veiculo] = relationship(lazy="selectin")
    usuario: Mapped[Usuario | None] = relationship(lazy="selectin")


class CompraCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    usuario_id: int | None = None
    data_compra: date | None = None
    valor_compra: Decimal
    debitos: Decimal | None = None
    observacoes: str | None = None
    status: StatusCompra = StatusCompra.pendente


class CompraUpdate(BaseModel):
    cliente_id: int | None = None
    veiculo_id: int | None = None
    data_compra: date | None = None
    valor_compra: Decimal | None = None
    debitos: Decimal | None = None
    observacoes: str | None = None
    status: StatusCompra | None = None


class CompraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente: ClienteRead
    veiculo: VeiculoRead
    usuario: UsuarioRead | None
    data_compra: date
    valor_compra: Decimal
    debitos: Decimal | None
    observacoes: str | None
    status: StatusCompra


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Compra]:
    return crud.list_all(session, Compra, limit=limit, offset=offset)


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


def list_by_cliente(session: Session, cliente_id: int) -> list[Compra]:
    return list(session.query(Compra).filter_by(cliente_id=cliente_id).all())


def create(session: Session, data: CompraCreate, actor_id: int | None = None) -> Compra:
    return crud.create(session, Compra, data, actor_id)


def update(
    session: Session, obj: Compra, data: CompraUpdate, actor_id: int | None = None
) -> Compra:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Compra, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def search(session: Session, term: str, column: str | None = None) -> list[Compra]:
    pattern = f"%{term}%"
    query = (
        session.query(Compra)
        .join(Cliente, Compra.cliente_id == Cliente.id)
        .join(Veiculo, Compra.veiculo_id == Veiculo.id)
    )

    columns_map = {
        "cliente": Cliente.nome,
        "documento": Cliente.documento,
        "modelo": Veiculo.modelo,
        "placa": Veiculo.placa,
        "data": Compra.data_compra,
        "valor": Compra.valor_compra,
        "status": Compra.status,
        "observacoes": Compra.observacoes,
    }

    if column and column in columns_map:
        col = columns_map[column]
        return list(query.where(cast(col, String).ilike(pattern)).distinct().all())

    return list(
        query.where(
            or_(
                Cliente.nome.ilike(pattern),
                Cliente.documento.ilike(pattern),
                Veiculo.modelo.ilike(pattern),
                Veiculo.placa.ilike(pattern),
                Compra.observacoes.ilike(pattern),
            )
        )
        .distinct()
        .all()
    )
