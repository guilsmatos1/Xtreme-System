"""Caixa dos investidores: lançamentos (aportes/custos), saldo, model, schemas, CRUD."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Numeric, case, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.veiculo.core import Veiculo


class TipoLancamento(StrEnum):
    aporte = "aporte"
    custo = "custo"


class OrigemLancamento(StrEnum):
    manual = "manual"
    veiculo = "veiculo"


class LancamentoCaixa(Base):
    __tablename__ = "lancamento_caixa"

    id: Mapped[int] = mapped_column(primary_key=True)
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"), index=True)
    veiculo_id: Mapped[int | None] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), unique=True, index=True
    )
    tipo: Mapped[TipoLancamento]  # noqa: SQLAlchemy mapped
    origem: Mapped[OrigemLancamento] = mapped_column(default=OrigemLancamento.manual)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    descricao: Mapped[str]  # noqa: SQLAlchemy mapped
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class LancamentoCaixaCreate(BaseModel):
    investidor_id: int
    tipo: TipoLancamento
    valor: Decimal = Field(gt=0)
    descricao: str


class LancamentoCaixaUpdate(BaseModel):
    tipo: TipoLancamento | None = None
    valor: Decimal | None = Field(default=None, gt=0)
    descricao: str | None = None


class LancamentoCaixaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investidor_id: int
    veiculo_id: int | None
    tipo: TipoLancamento
    origem: OrigemLancamento
    valor: Decimal
    descricao: str
    criado_em: datetime


def list_all(session: Session) -> list[LancamentoCaixa]:
    return crud.list_all(session, LancamentoCaixa)


def get(session: Session, lancamento_id: int) -> LancamentoCaixa | None:
    return crud.get(session, LancamentoCaixa, lancamento_id)


def create(session: Session, data: LancamentoCaixaCreate) -> LancamentoCaixa:
    return crud.create(session, LancamentoCaixa, data)


def update(
    session: Session, obj: LancamentoCaixa, data: LancamentoCaixaUpdate
) -> LancamentoCaixa:
    return crud.update(session, obj, data)


def delete(session: Session, obj: LancamentoCaixa) -> None:
    crud.delete(session, obj)


def list_by_investidor(session: Session, investidor_id: int) -> list[LancamentoCaixa]:
    return list(
        session.query(LancamentoCaixa)
        .filter_by(investidor_id=investidor_id)
        .order_by(LancamentoCaixa.id)
        .all()
    )


_SALDO_EXPR = func.sum(
    case(
        (LancamentoCaixa.tipo == TipoLancamento.aporte, LancamentoCaixa.valor),
        else_=-LancamentoCaixa.valor,
    )
)


def saldo(session: Session, investidor_id: int) -> Decimal:
    valor = session.query(_SALDO_EXPR).filter_by(investidor_id=investidor_id).scalar()
    return valor or Decimal("0")


def saldos(session: Session) -> dict[int, Decimal]:
    rows = (
        session.query(LancamentoCaixa.investidor_id, _SALDO_EXPR)
        .group_by(LancamentoCaixa.investidor_id)
        .all()
    )
    return {investidor_id: total for investidor_id, total in rows}  # noqa: C416


def _descricao_veiculo(veiculo_obj: Veiculo) -> str:
    return f"Compra do veículo {veiculo_obj.modelo} - placa {veiculo_obj.placa}"


def criar_lancamento_veiculo(session: Session, veiculo_obj: Veiculo) -> LancamentoCaixa:
    obj = LancamentoCaixa(
        investidor_id=veiculo_obj.investidor_id,
        veiculo_id=veiculo_obj.id,
        tipo=TipoLancamento.custo,
        origem=OrigemLancamento.veiculo,
        valor=veiculo_obj.preco,
        descricao=_descricao_veiculo(veiculo_obj),
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def sincronizar_lancamento_veiculo(session: Session, veiculo_obj: Veiculo) -> None:
    lancamento = (
        session.query(LancamentoCaixa)
        .filter_by(veiculo_id=veiculo_obj.id)
        .one_or_none()
    )
    if lancamento is None:
        return
    lancamento.valor = veiculo_obj.preco
    lancamento.investidor_id = veiculo_obj.investidor_id
    lancamento.descricao = _descricao_veiculo(veiculo_obj)
    session.commit()
