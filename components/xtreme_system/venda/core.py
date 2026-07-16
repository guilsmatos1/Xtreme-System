"""Venda: enum de status, model (com FKs), schemas e CRUD."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Date, ForeignKey, Numeric, extract, false, func
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
    data_venda: Mapped[date | None] = mapped_column(Date)
    valor_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_entrada: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    km: Mapped[int | None] = mapped_column()
    forma_pagamento: Mapped[str]
    parcelas: Mapped[int]
    status: Mapped[StatusVenda] = mapped_column(default=StatusVenda.pendente)
    observacoes: Mapped[str | None]
    veiculo_troca_id: Mapped[int | None] = mapped_column(
        ForeignKey("veiculo.id"), index=True
    )
    valor_diferenca: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pagamento_pendente: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    valor_pendente: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    datas_pagamento: Mapped[str | None]

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    veiculo: Mapped[Veiculo] = relationship(lazy="joined", foreign_keys=[veiculo_id])
    veiculo_troca: Mapped[Veiculo | None] = relationship(
        lazy="joined", foreign_keys=[veiculo_troca_id]
    )
    vendedor: Mapped[Usuario | None] = relationship(lazy="joined")


class VendaCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    vendedor_id: int | None = None
    data_venda: date | None = None
    valor_venda: Decimal
    valor_entrada: Decimal | None = None
    debitos: Decimal | None = None
    km: int | None = None
    forma_pagamento: str
    parcelas: int
    status: StatusVenda = StatusVenda.pendente
    observacoes: str | None = None
    veiculo_troca_id: int | None = None
    valor_diferenca: Decimal | None = None
    pagamento_pendente: bool = False
    valor_pendente: Decimal | None = None
    datas_pagamento: str | None = None


class VendaUpdate(BaseModel):
    cliente_id: int | None = None
    veiculo_id: int | None = None
    vendedor_id: int | None = None
    data_venda: date | None = None
    valor_venda: Decimal | None = None
    valor_entrada: Decimal | None = None
    debitos: Decimal | None = None
    km: int | None = None
    forma_pagamento: str | None = None
    parcelas: int | None = None
    status: StatusVenda | None = None
    observacoes: str | None = None
    veiculo_troca_id: int | None = None
    valor_diferenca: Decimal | None = None
    pagamento_pendente: bool = False
    valor_pendente: Decimal | None = None
    datas_pagamento: str | None = None


class VendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente: ClienteRead
    veiculo: VeiculoRead
    veiculo_troca: VeiculoRead | None
    vendedor: UsuarioRead | None
    data_venda: date | None
    valor_venda: Decimal
    valor_entrada: Decimal | None
    debitos: Decimal | None
    km: int | None
    forma_pagamento: str
    parcelas: int
    status: StatusVenda
    observacoes: str | None
    valor_diferenca: Decimal | None
    pagamento_pendente: bool
    valor_pendente: Decimal | None
    datas_pagamento: str | None


def list_all(session: Session) -> list[Venda]:
    return crud.list_all(session, Venda)


def get(session: Session, venda_id: int) -> Venda | None:
    return crud.get(session, Venda, venda_id)


def list_by_cliente(session: Session, cliente_id: int) -> list[Venda]:
    return list(session.query(Venda).filter_by(cliente_id=cliente_id).all())


def _status_veiculo_para_venda(status: StatusVenda) -> StatusVeiculo:
    if status == StatusVenda.concluido:
        return StatusVeiculo.vendido
    return StatusVeiculo.disponivel


def veiculo_tem_outra_venda_concluida(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    query = session.query(Venda).filter(
        Venda.veiculo_id == veiculo_id,
        Venda.status == StatusVenda.concluido,
    )
    if excluir_venda_id is not None:
        query = query.filter(Venda.id != excluir_venda_id)
    return query.first() is not None


def _sincronizar_status_veiculo(
    session: Session,
    obj: Venda,
    *,
    veiculo_anterior_id: int | None = None,
    status_anterior: StatusVenda | None = None,
) -> Venda:
    status_veiculo = _status_veiculo_para_venda(obj.status)
    if (
        veiculo_anterior_id is not None
        and veiculo_anterior_id != obj.veiculo_id
        and status_anterior == StatusVenda.concluido
    ):
        veiculo_anterior = session.get(Veiculo, veiculo_anterior_id)
        if veiculo_anterior is not None:
            if veiculo_tem_outra_venda_concluida(
                session, veiculo_anterior_id, excluir_venda_id=obj.id
            ):
                veiculo_anterior.status = StatusVeiculo.vendido
            else:
                veiculo_anterior.status = StatusVeiculo.disponivel
    if status_veiculo == StatusVeiculo.disponivel and veiculo_tem_outra_venda_concluida(
        session, obj.veiculo_id, excluir_venda_id=obj.id
    ):
        obj.veiculo.status = StatusVeiculo.vendido
    else:
        obj.veiculo.status = status_veiculo
    crud.flush(session)
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


def tendencia_por_periodo(
    session: Session, periodo: str
) -> list[tuple[str, int, Decimal]]:
    """Retorna vendas agregadas por semana (30d/90d) ou mês (12m)."""
    hoje = datetime.now(UTC).date()
    if periodo == "12m":
        mes_inicial = hoje.month - 11
        ano_inicial = hoje.year
        if mes_inicial <= 0:
            mes_inicial += 12
            ano_inicial -= 1
        inicio = date(ano_inicial, mes_inicial, 1)
        granularidade = "mes"
    elif periodo == "90d":
        inicio = hoje - timedelta(days=89)
        granularidade = "semana"
    else:
        inicio = hoje - timedelta(days=29)
        granularidade = "semana"

    base = (
        session.query(Venda)
        .filter(Venda.data_venda >= inicio)
        .filter(Venda.data_venda.isnot(None))
        .filter(Venda.status != StatusVenda.cancelado)
    )

    if granularidade == "mes":
        ano_expr = extract("year", Venda.data_venda)
        mes_expr = extract("month", Venda.data_venda)
        rows = (
            base.with_entities(
                ano_expr.label("ano"),
                mes_expr.label("mes"),
                func.count(Venda.id).label("count"),
                func.sum(Venda.valor_venda).label("total"),
            )
            .group_by(ano_expr, mes_expr)
            .order_by(ano_expr, mes_expr)
            .all()
        )
        return [
            (f"{ano:04d}-{mes:02d}", count or 0, total or Decimal("0"))
            for ano, mes, count, total in rows
        ]

    ano_expr = extract("year", Venda.data_venda)
    mes_expr = extract("month", Venda.data_venda)
    dia_expr = extract("day", Venda.data_venda)
    dia_rows = (
        base.with_entities(
            ano_expr.label("ano"),
            mes_expr.label("mes"),
            dia_expr.label("dia"),
            func.count(Venda.id).label("count"),
            func.sum(Venda.valor_venda).label("total"),
        )
        .group_by(ano_expr, mes_expr, dia_expr)
        .order_by(ano_expr, mes_expr, dia_expr)
        .all()
    )

    grupos: dict[str, tuple[int, Decimal]] = {}
    for ano, mes, dia, count, total in dia_rows:
        data_venda = date(ano, mes, dia)
        iso_ano, iso_semana, _ = data_venda.isocalendar()
        chave = f"{iso_ano:04d}-S{iso_semana:02d}"
        prev_count, prev_total = grupos.get(chave, (0, Decimal("0")))
        grupos[chave] = prev_count + count, prev_total + total

    return [(chave, count, total) for chave, (count, total) in grupos.items()]
