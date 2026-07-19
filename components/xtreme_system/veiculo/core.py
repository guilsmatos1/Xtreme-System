"""Veículo: enums, model (com FKs), schemas e CRUD."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, Numeric, func, or_
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.documento_procuracao.core import DocumentoProcuracao
from xtreme_system.documento_veiculo.core import DocumentoVeiculo
from xtreme_system.imagem_veiculo.core import ImagemVeiculo
from xtreme_system.investidor.core import Investidor, InvestidorRead


class TipoVeiculo(StrEnum):
    moto = "moto"
    carro = "carro"


class StatusVeiculo(StrEnum):
    disponivel = "disponivel"
    vendido = "vendido"
    reservado = "reservado"


class TipoEntrada(StrEnum):
    compra = "compra"
    consignacao = "consignacao"


class Veiculo(Base):
    __tablename__ = "veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoVeiculo]
    modelo: Mapped[str]
    cor: Mapped[str]
    ano: Mapped[int]
    placa: Mapped[str] = mapped_column(unique=True, index=True)
    km: Mapped[int | None]
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    procuracao: Mapped[str | None]
    status: Mapped[StatusVeiculo] = mapped_column(default=StatusVeiculo.disponivel)
    tipo_entrada: Mapped[TipoEntrada] = mapped_column(default=TipoEntrada.compra)
    revisao: Mapped[bool] = mapped_column(default=False)
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"), index=True)

    investidor: Mapped[Investidor] = relationship(lazy="joined")
    imagens: Mapped[list["ImagemVeiculo"]] = relationship(cascade="all, delete-orphan")
    documentos: Mapped[list["DocumentoVeiculo"]] = relationship(
        cascade="all, delete-orphan"
    )
    documentos_procuracao: Mapped[list["DocumentoProcuracao"]] = relationship(
        cascade="all, delete-orphan"
    )


class VeiculoCreate(BaseModel):
    tipo: TipoVeiculo
    modelo: str
    cor: str
    ano: int
    placa: str
    km: int | None = None
    preco: Decimal
    procuracao: str | None = None
    status: StatusVeiculo = StatusVeiculo.disponivel
    tipo_entrada: TipoEntrada = TipoEntrada.compra
    revisao: bool = False
    investidor_id: int


class VeiculoUpdate(BaseModel):
    tipo: TipoVeiculo | None = None
    modelo: str | None = None
    cor: str | None = None
    ano: int | None = None
    placa: str | None = None
    km: int | None = None
    preco: Decimal | None = None
    procuracao: str | None = None
    status: StatusVeiculo | None = None
    tipo_entrada: TipoEntrada | None = None
    revisao: bool | None = None
    investidor_id: int | None = None


class VeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoVeiculo
    modelo: str
    cor: str
    ano: int
    placa: str
    km: int | None = None
    preco: Decimal
    procuracao: str | None
    status: StatusVeiculo
    tipo_entrada: TipoEntrada
    revisao: bool
    investidor: InvestidorRead


def list_all(session: Session) -> list[Veiculo]:
    return crud.list_all(session, Veiculo)


def get(session: Session, veiculo_id: int) -> Veiculo | None:
    return crud.get(session, Veiculo, veiculo_id)


def create(
    session: Session, data: VeiculoCreate, actor_id: int | None = None
) -> Veiculo:
    return crud.create(session, Veiculo, data, actor_id)


def update(
    session: Session, obj: Veiculo, data: VeiculoUpdate, actor_id: int | None = None
) -> Veiculo:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Veiculo, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def get_by_placa(session: Session, placa: str) -> Veiculo | None:
    return session.query(Veiculo).filter_by(placa=placa).one_or_none()


def search(session: Session, term: str) -> list[Veiculo]:
    pattern = f"%{term}%"
    return list(
        session.query(Veiculo)
        .where(
            or_(
                Veiculo.modelo.ilike(pattern),
                Veiculo.placa.ilike(pattern),
                Veiculo.cor.ilike(pattern),
            )
        )
        .all()
    )


def resumo_estoque(session: Session) -> dict[StatusVeiculo, tuple[int, Decimal]]:
    """Retorna (contagem, soma de preco) por status de veículo."""
    rows = (
        session.query(Veiculo.status, func.count(Veiculo.id), func.sum(Veiculo.preco))
        .group_by(Veiculo.status)
        .all()
    )
    return {
        status: (count or 0, total or Decimal("0")) for status, count, total in rows
    }
