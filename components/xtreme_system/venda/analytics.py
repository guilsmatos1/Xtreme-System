"""Read-only sales analytics for dashboards and reports."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from xtreme_system.usuario.core import Usuario
from xtreme_system.veiculo.core import TipoVeiculo, Veiculo
from xtreme_system.venda.core import (
    VENDA_NAO_CANCELADA,
    StatusVenda,
    Venda,
)


def _mes_atual_inicio() -> date:
    hoje = datetime.now(UTC).date()
    return hoje.replace(day=1)


def _inicio_janela_meses(hoje: date, meses: int) -> date:
    """Retorna o primeiro dia do mês que inicia uma janela inclusiva."""
    deslocamento = meses - 1
    ano, mes = divmod(hoje.year * 12 + hoje.month - 1 - deslocamento, 12)
    return date(ano, mes + 1, 1)


def resumo_mes(session: Session) -> tuple[int, Decimal]:
    """Retorna (contagem, soma) de vendas do mês atual com status != cancelado."""
    resultado = (
        session.query(func.count(Venda.id), func.sum(Venda.valor_venda))
        .filter(Venda.data_venda >= _mes_atual_inicio())
        .filter(VENDA_NAO_CANCELADA)
        .all()
    )
    count, total = resultado[0] if resultado else (0, None)
    return count or 0, total or Decimal("0")


def ticket_medio(session: Session) -> Decimal:
    """Retorna valor médio de venda com status != cancelado."""
    valor = (
        session.query(func.avg(Venda.valor_venda)).filter(VENDA_NAO_CANCELADA).scalar()
    )
    return valor or Decimal("0")


def receita_por_tipo(session: Session) -> dict[TipoVeiculo, Decimal]:
    """Retorna soma de valor_venda agrupada por tipo de veículo, sem cancelados."""
    rows = (
        session.query(Veiculo.tipo, func.sum(Venda.valor_venda))
        .join(Venda, Venda.veiculo_id == Veiculo.id)
        .filter(VENDA_NAO_CANCELADA)
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
        .filter(VENDA_NAO_CANCELADA)
        .group_by(Usuario.id)
        .order_by(func.sum(Venda.valor_venda).desc(), Usuario.id.asc())
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
        inicio = _inicio_janela_meses(hoje, 12)
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
        .filter(VENDA_NAO_CANCELADA)
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


MESES_ABREV = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]


def desempenho_vendas_mensal(
    session: Session, meses: int = 6
) -> list[tuple[str, int, Decimal]]:
    """Retorna (label, count, total) dos últimos N meses, incluindo meses sem vendas."""
    hoje = datetime.now(UTC).date()
    inicio = _inicio_janela_meses(hoje, meses)
    ano_inicial, mes_inicial = inicio.year, inicio.month

    ano_expr = extract("year", Venda.data_venda)
    mes_expr = extract("month", Venda.data_venda)
    rows = (
        session.query(
            ano_expr.label("ano"),
            mes_expr.label("mes"),
            func.count(Venda.id).label("count"),
            func.sum(Venda.valor_venda).label("total"),
        )
        .filter(Venda.data_venda >= inicio)
        .filter(Venda.data_venda.isnot(None))
        .filter(VENDA_NAO_CANCELADA)
        .group_by(ano_expr, mes_expr)
        .all()
    )
    por_chave = {
        (int(ano), int(mes)): (count or 0, total or Decimal("0"))
        for ano, mes, count, total in rows
    }

    resultado: list[tuple[str, int, Decimal]] = []
    ano, mes = ano_inicial, mes_inicial
    for _ in range(meses):
        count, total = por_chave.get((ano, mes), (0, Decimal("0")))
        resultado.append((f"{MESES_ABREV[mes - 1]}/{ano % 100:02d}", count, total))
        mes += 1
        if mes > len(MESES_ABREV):
            mes = 1
            ano += 1
    return resultado
