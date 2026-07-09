"""Veículo: enums, model (com FKs), schemas e CRUD."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, Numeric, or_
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.investidor.core import Investidor, InvestidorRead
from xtreme_system.meio_captacao.core import MeioCaptacao, MeioCaptacaoRead


class TipoVeiculo(StrEnum):
    moto = "moto"  # noqa: enum member
    carro = "carro"


class StatusVeiculo(StrEnum):
    disponivel = "disponivel"
    vendido = "vendido"
    reservado = "reservado"


class Veiculo(Base):
    __tablename__ = "veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoVeiculo]  # noqa: SQLAlchemy mapped
    modelo: Mapped[str]  # noqa: SQLAlchemy mapped
    cor: Mapped[str]  # noqa: SQLAlchemy mapped
    ano: Mapped[int]  # noqa: SQLAlchemy mapped
    placa: Mapped[str] = mapped_column(unique=True, index=True)  # noqa: SQLAlchemy mapped
    km: Mapped[int]  # noqa: SQLAlchemy mapped
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # noqa: SQLAlchemy mapped
    procuracao: Mapped[str | None]  # noqa: SQLAlchemy mapped
    status: Mapped[StatusVeiculo] = mapped_column(default=StatusVeiculo.disponivel)
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"), index=True)
    meio_captacao_id: Mapped[int] = mapped_column(
        ForeignKey("meio_captacao.id"), index=True
    )

    investidor: Mapped[Investidor] = relationship(lazy="joined")
    meio_captacao: Mapped[MeioCaptacao] = relationship(lazy="joined")


class VeiculoCreate(BaseModel):
    tipo: TipoVeiculo  # noqa: Pydantic field
    modelo: str  # noqa: Pydantic field
    cor: str  # noqa: Pydantic field
    ano: int  # noqa: Pydantic field
    placa: str  # noqa: Pydantic field
    km: int  # noqa: Pydantic field
    preco: Decimal  # noqa: Pydantic field
    procuracao: str | None = None  # noqa: Pydantic field
    status: StatusVeiculo = StatusVeiculo.disponivel
    investidor_id: int
    meio_captacao_id: int


class VeiculoUpdate(BaseModel):
    tipo: TipoVeiculo | None = None  # noqa: Pydantic field
    modelo: str | None = None  # noqa: Pydantic field
    cor: str | None = None  # noqa: Pydantic field
    ano: int | None = None  # noqa: Pydantic field
    placa: str | None = None  # noqa: Pydantic field
    km: int | None = None  # noqa: Pydantic field
    preco: Decimal | None = None  # noqa: Pydantic field
    procuracao: str | None = None  # noqa: Pydantic field
    status: StatusVeiculo | None = None
    investidor_id: int | None = None
    meio_captacao_id: int | None = None


class VeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # noqa: Pydantic field
    tipo: TipoVeiculo  # noqa: Pydantic field
    modelo: str  # noqa: Pydantic field
    cor: str  # noqa: Pydantic field
    ano: int  # noqa: Pydantic field
    placa: str  # noqa: Pydantic field
    km: int  # noqa: Pydantic field
    preco: Decimal  # noqa: Pydantic field
    procuracao: str | None  # noqa: Pydantic field
    status: StatusVeiculo  # noqa: Pydantic field
    investidor: InvestidorRead  # noqa: Pydantic field
    meio_captacao: MeioCaptacaoRead  # noqa: Pydantic field


def list_all(session: Session) -> list[Veiculo]:
    return crud.list_all(session, Veiculo)


def get(session: Session, veiculo_id: int) -> Veiculo | None:
    return crud.get(session, Veiculo, veiculo_id)


def create(session: Session, data: VeiculoCreate) -> Veiculo:
    return crud.create(session, Veiculo, data)


def update(session: Session, obj: Veiculo, data: VeiculoUpdate) -> Veiculo:
    return crud.update(session, obj, data)


def delete(session: Session, obj: Veiculo) -> None:
    crud.delete(session, obj)


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
