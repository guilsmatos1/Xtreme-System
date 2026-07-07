"""Veículo: enums, model (com FKs), schemas e CRUD."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.database.core import Base
from xtreme_system.investidor.core import Investidor, InvestidorRead
from xtreme_system.meio_captacao.core import MeioCaptacao, MeioCaptacaoRead


class TipoVeiculo(StrEnum):
    moto = "moto"
    carro = "carro"


class StatusVeiculo(StrEnum):
    disponivel = "disponivel"
    vendido = "vendido"


class Veiculo(Base):
    __tablename__ = "veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoVeiculo]
    modelo: Mapped[str]
    cor: Mapped[str]
    ano: Mapped[int]
    placa: Mapped[str] = mapped_column(unique=True, index=True)
    km: Mapped[int]
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    procuracao: Mapped[str | None]
    status: Mapped[StatusVeiculo] = mapped_column(default=StatusVeiculo.disponivel)
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"))
    meio_captacao_id: Mapped[int] = mapped_column(ForeignKey("meio_captacao.id"))

    investidor: Mapped[Investidor] = relationship(lazy="joined")
    meio_captacao: Mapped[MeioCaptacao] = relationship(lazy="joined")


class VeiculoCreate(BaseModel):
    tipo: TipoVeiculo
    modelo: str
    cor: str
    ano: int
    placa: str
    km: int
    preco: Decimal
    procuracao: str | None = None
    status: StatusVeiculo = StatusVeiculo.disponivel
    investidor_id: int
    meio_captacao_id: int


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
    investidor_id: int | None = None
    meio_captacao_id: int | None = None


class VeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoVeiculo
    modelo: str
    cor: str
    ano: int
    placa: str
    km: int
    preco: Decimal
    procuracao: str | None
    status: StatusVeiculo
    investidor: InvestidorRead
    meio_captacao: MeioCaptacaoRead


def list_all(session: Session) -> list[Veiculo]:
    return list(session.query(Veiculo).all())


def get(session: Session, veiculo_id: int) -> Veiculo | None:
    return session.get(Veiculo, veiculo_id)


def create(session: Session, data: VeiculoCreate) -> Veiculo:
    obj = Veiculo(**data.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def update(session: Session, obj: Veiculo, data: VeiculoUpdate) -> Veiculo:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    session.commit()
    session.refresh(obj)
    return obj


def delete(session: Session, obj: Veiculo) -> None:
    session.delete(obj)
    session.commit()
