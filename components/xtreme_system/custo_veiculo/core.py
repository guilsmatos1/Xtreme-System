"""Custo de veículo: custos operacionais sem impacto no saldo do investidor."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.veiculo.core import Veiculo, VeiculoRead


class CustoVeiculo(Base):
    __tablename__ = "custo_veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    categoria: Mapped[str]
    descricao: Mapped[str | None]
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data_custo: Mapped[date] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    veiculo: Mapped[Veiculo] = relationship(lazy="joined")


class CustoVeiculoCreate(BaseModel):
    veiculo_id: int
    categoria: str = Field(min_length=1)
    descricao: str | None = None
    valor: Decimal = Field(gt=0)
    data_custo: date


class CustoVeiculoUpdate(BaseModel):
    veiculo_id: int | None = None
    categoria: str | None = Field(default=None, min_length=1)
    descricao: str | None = None
    valor: Decimal | None = Field(default=None, gt=0)
    data_custo: date | None = None


class CustoVeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    veiculo: VeiculoRead
    categoria: str
    descricao: str | None
    valor: Decimal
    data_custo: date
    criado_em: datetime


def list_all(session: Session) -> list[CustoVeiculo]:
    return crud.list_all(session, CustoVeiculo)


def get(session: Session, custo_id: int) -> CustoVeiculo | None:
    return crud.get(session, CustoVeiculo, custo_id)


def create(session: Session, data: CustoVeiculoCreate) -> CustoVeiculo:
    return crud.create(session, CustoVeiculo, data)


def update(
    session: Session, obj: CustoVeiculo, data: CustoVeiculoUpdate
) -> CustoVeiculo:
    return crud.update(session, obj, data)


def delete(session: Session, obj: CustoVeiculo) -> None:
    crud.delete(session, obj)
