"""Caixa dos investidores: lançamentos (aportes/custos), saldo, model, schemas, CRUD."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Numeric, case, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.auditoria.core import _snapshot, auditar
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.veiculo.core import Veiculo


class TipoLancamento(StrEnum):
    aporte = "aporte"
    custo = "custo"
    receita_venda = "receita_venda"
    distribuicao_lucro = "distribuicao_lucro"


class OrigemLancamento(StrEnum):
    manual = "manual"
    veiculo = "veiculo"
    fechamento_venda = "fechamento_venda"


class LancamentoInvestimento(Base):
    __tablename__ = "lancamento_investimento"

    id: Mapped[int] = mapped_column(primary_key=True)
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"), index=True)
    veiculo_id: Mapped[int | None] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), unique=True, index=True
    )
    fechamento_venda_id: Mapped[int | None] = mapped_column(
        ForeignKey("fechamento_venda.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoLancamento]
    origem: Mapped[OrigemLancamento] = mapped_column(default=OrigemLancamento.manual)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    descricao: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class LancamentoInvestimentoCreate(BaseModel):
    investidor_id: int
    tipo: TipoLancamento
    valor: Decimal = Field(gt=0)
    descricao: str | None = None


class LancamentoInvestimentoUpdate(BaseModel):
    tipo: TipoLancamento | None = None
    valor: Decimal | None = Field(default=None, gt=0)
    descricao: str | None = None


class LancamentoInvestimentoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investidor_id: int
    veiculo_id: int | None
    fechamento_venda_id: int | None
    tipo: TipoLancamento
    origem: OrigemLancamento
    valor: Decimal
    descricao: str
    criado_em: datetime


def list_all(session: Session) -> list[LancamentoInvestimento]:
    return crud.list_all(session, LancamentoInvestimento)


def get(session: Session, lancamento_id: int) -> LancamentoInvestimento | None:
    return crud.get(session, LancamentoInvestimento, lancamento_id)


def create(
    session: Session, data: LancamentoInvestimentoCreate
) -> LancamentoInvestimento:
    return crud.create(session, LancamentoInvestimento, data)


def update(
    session: Session, obj: LancamentoInvestimento, data: LancamentoInvestimentoUpdate
) -> LancamentoInvestimento:
    return crud.update(session, obj, data)


def delete(session: Session, obj: LancamentoInvestimento) -> None:
    crud.delete(session, obj)


def list_by_investidor(
    session: Session, investidor_id: int
) -> list[LancamentoInvestimento]:
    return list(
        session.query(LancamentoInvestimento)
        .filter_by(investidor_id=investidor_id)
        .order_by(LancamentoInvestimento.id)
        .all()
    )


_SALDO_EXPR = func.sum(
    case(
        (
            LancamentoInvestimento.tipo == TipoLancamento.aporte,
            LancamentoInvestimento.valor,
        ),
        (
            LancamentoInvestimento.tipo == TipoLancamento.receita_venda,
            LancamentoInvestimento.valor,
        ),
        else_=-LancamentoInvestimento.valor,
    )
)


def saldo(session: Session, investidor_id: int) -> Decimal:
    valor = session.query(_SALDO_EXPR).filter_by(investidor_id=investidor_id).scalar()
    return valor or Decimal("0")


def saldos(session: Session) -> dict[int, Decimal]:
    rows = (
        session.query(LancamentoInvestimento.investidor_id, _SALDO_EXPR)
        .group_by(LancamentoInvestimento.investidor_id)
        .all()
    )
    return {investidor_id: total for investidor_id, total in rows}  # noqa: C416


def _descricao_veiculo(veiculo_obj: Veiculo) -> str:
    return f"Compra do veículo {veiculo_obj.modelo} - placa {veiculo_obj.placa}"


def criar_lancamento_veiculo(
    session: Session, veiculo_obj: Veiculo
) -> LancamentoInvestimento:
    obj = LancamentoInvestimento(
        investidor_id=veiculo_obj.investidor_id,
        veiculo_id=veiculo_obj.id,
        fechamento_venda_id=None,
        tipo=TipoLancamento.custo,
        origem=OrigemLancamento.veiculo,
        valor=veiculo_obj.preco,
        descricao=_descricao_veiculo(veiculo_obj),
    )
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        tabela="lancamento_investimento",
        tipo_acao="CREATE",
        registro_id=obj.id,
        dados_depois=_snapshot(obj),
    )
    crud.flush(session)
    return obj


def sincronizar_lancamento_veiculo(session: Session, veiculo_obj: Veiculo) -> None:
    lancamento = (
        session.query(LancamentoInvestimento)
        .filter_by(veiculo_id=veiculo_obj.id)
        .one_or_none()
    )
    if lancamento is None:
        return
    antes = _snapshot(lancamento)
    lancamento.valor = veiculo_obj.preco
    lancamento.investidor_id = veiculo_obj.investidor_id
    lancamento.descricao = _descricao_veiculo(veiculo_obj)
    session.flush()
    auditar(
        session,
        tabela="lancamento_investimento",
        tipo_acao="UPDATE",
        registro_id=lancamento.id,
        dados_antes=antes,
        dados_depois=_snapshot(lancamento),
    )
    crud.flush(session)


def deletar_lancamento_veiculo(session: Session, veiculo_obj: Veiculo) -> None:
    """Delete o lançamento do veículo via ORM antes do DB cascatear a FK, p/ auditar."""
    lancamento = (
        session.query(LancamentoInvestimento)
        .filter_by(veiculo_id=veiculo_obj.id)
        .one_or_none()
    )
    if lancamento is not None:
        crud.delete(session, lancamento)


# In-memory aggregations for caixa table. Query-level if row counts grow.
def agregados_investidores(
    session: Session,
) -> tuple[dict[int, int], dict[int, Decimal], dict[int, Decimal]]:
    """Return (num_veiculos, valor_veiculos, total_aportado) per investidor_id."""
    veiculos = crud.list_all(session, Veiculo)
    num: dict[int, int] = {}
    valor: dict[int, Decimal] = {}
    for v in veiculos:
        iid = v.investidor_id
        num[iid] = num.get(iid, 0) + 1
        valor[iid] = valor.get(iid, Decimal("0")) + v.preco
    aportes: dict[int, Decimal] = {}
    for lanc in list_all(session):
        aportes[lanc.investidor_id] = aportes.get(lanc.investidor_id, Decimal("0")) + (
            lanc.valor
            if lanc.tipo in {TipoLancamento.aporte, TipoLancamento.receita_venda}
            else -lanc.valor
        )
    return num, valor, aportes


def criar_lancamento_fechamento(
    session: Session,
    *,
    investidor_id: int,
    fechamento_venda_id: int,
    tipo: TipoLancamento,
    valor: Decimal,
    descricao: str,
) -> LancamentoInvestimento:
    obj = LancamentoInvestimento(
        investidor_id=investidor_id,
        veiculo_id=None,
        fechamento_venda_id=fechamento_venda_id,
        tipo=tipo,
        origem=OrigemLancamento.fechamento_venda,
        valor=valor,
        descricao=descricao,
    )
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        tabela="lancamento_investimento",
        tipo_acao="CREATE",
        registro_id=obj.id,
        dados_depois=_snapshot(obj),
    )
    crud.flush(session)
    return obj
