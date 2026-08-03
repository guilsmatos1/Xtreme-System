"""HTMX routes for dashboard."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.setup import app
from xtreme_system.auditoria import core as auditoria
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import analytics as venda_analytics
from xtreme_system.venda import core as venda

# ---- Dashboard (KPIs, admin-only) ----


MESES_DROPDOWN = 24


def _eixo_max(valor: Decimal) -> Decimal:
    """Arredonda para cima para um valor "redondo" (1/2/2.5/5/10 x potência de 10)."""
    if valor <= 0:
        return Decimal("100")
    potencia = Decimal(10) ** (len(str(int(valor))) - 1)
    multiplicadores = (
        Decimal("1"),
        Decimal("2"),
        Decimal("2.5"),
        Decimal("5"),
        Decimal("10"),
    )
    for mult in multiplicadores:
        candidato = mult * potencia
        if candidato >= valor:
            return candidato
    return potencia * 10


def _mes_atual() -> date:
    hoje = datetime.now(UTC).date()
    return hoje.replace(day=1)


def _parse_mes(mes: str | None) -> date:
    if not mes:
        return _mes_atual()
    try:
        parsed = datetime.strptime(mes, "%Y-%m")  # noqa: DTZ007
        return parsed.date().replace(day=1)
    except ValueError:
        return _mes_atual()


def _somar_meses(inicio: date, meses: int) -> date:
    total = inicio.year * 12 + inicio.month - 1 + meses
    return date(total // 12, total % 12 + 1, 1)


def _opcoes_meses(mes_selecionado: date) -> list[dict[str, str]]:
    atual = _mes_atual()
    meses = [_somar_meses(atual, -idx) for idx in range(MESES_DROPDOWN)]
    if mes_selecionado not in meses:
        meses.append(mes_selecionado)
    return [
        {"value": mes.isoformat()[:7], "label": mes.strftime("%m/%Y")}
        for mes in sorted(meses, reverse=True)
    ]


def _resumo_ticket_vendas_mes(
    session: Session, inicio: date
) -> tuple[int, Decimal, Decimal]:
    fim = _somar_meses(inicio, 1)
    count, total, ticket_medio = (
        session.query(
            func.count(venda.Venda.id),
            func.sum(venda.Venda.valor_venda),
            func.avg(venda.Venda.valor_venda),
        )
        .filter(venda.Venda.data_venda >= inicio)
        .filter(venda.Venda.data_venda < fim)
        .filter(venda.Venda.status != venda.StatusVenda.cancelado)
        .one()
    )
    return count or 0, total or Decimal("0"), ticket_medio or Decimal("0")


def _atividade_titulo(row: auditoria.Auditoria) -> str:
    acao = {
        "CREATE": "registrada",
        "UPDATE": "atualizada",
        "DELETE": "removida",
    }.get(row.tipo_acao, row.tipo_acao.lower())
    tabela = row.tabela.replace("_", " ").capitalize()
    if row.tabela == "venda" and row.tipo_acao == "UPDATE":
        antes = (row.dados_antes or {}).get("status")
        depois = (row.dados_depois or {}).get("status")
        if antes != depois and depois == venda.StatusVenda.cancelado.value:
            return f"Venda #{row.registro_id} cancelada"
    if row.tabela.startswith("documento") and row.tipo_acao == "CREATE":
        return "Documento gerado"
    if row.registro_id:
        return f"{tabela} #{row.registro_id} {acao}"
    return f"{tabela} {acao}"


def _atividades_recentes(session: Session) -> list[dict[str, str]]:
    def _nome_usuario(usuario_id: int | None) -> str:
        if not usuario_id:
            return "Sistema"
        usu = usuario.get(session, usuario_id)
        return usu.username if usu else "Sistema"

    return [
        {
            "titulo": _atividade_titulo(row),
            "detalhe": f"{row.tabela} · {row.tipo_acao}",
            "usuario": _nome_usuario(row.usuario_id),
            "quando": row.criado_em.strftime("%d/%m/%Y %H:%M"),
        }
        for row in auditoria.query(session, limit=8)
    ]


def _ctx_dashboard(session: Session, mes: str | None = None) -> dict[str, Any]:
    mes_inicio = _parse_mes(mes)

    resumo = veiculo.resumo_estoque(session)
    disponiveis, valor_estoque = resumo.get(
        veiculo.StatusVeiculo.disponivel, (0, Decimal("0"))
    )

    vendas_mes_count, vendas_mes_total, ticket_medio = _resumo_ticket_vendas_mes(
        session, mes_inicio
    )

    desempenho_mensal = venda_analytics.desempenho_vendas_mensal(session, 6)
    maior_total = max(
        (total for _, _, total in desempenho_mensal), default=Decimal("0")
    )
    eixo_max = _eixo_max(maior_total)
    desempenho_chart = [
        {
            "label": label,
            "count": count,
            "total": total,
            "pct": float(total / eixo_max * 100) if eixo_max else 0,
        }
        for label, count, total in desempenho_mensal
    ]
    fatores_eixo_y = (
        Decimal("1"),
        Decimal("0.75"),
        Decimal("0.5"),
        Decimal("0.25"),
        Decimal("0"),
    )
    eixo_y_ticks = [eixo_max * fator for fator in fatores_eixo_y]

    return {
        "titulo": "Dashboard",
        "mes": mes_inicio.isoformat()[:7],
        "meses": _opcoes_meses(mes_inicio),
        "disponiveis": disponiveis,
        "total_veiculos": disponiveis,
        "valor_estoque": valor_estoque,
        "vendas_mes_count": vendas_mes_count,
        "vendas_mes_total": vendas_mes_total,
        "ticket_medio": ticket_medio,
        "ranking_vendedores": venda_analytics.ranking_vendedores(session),
        "atividades_recentes": _atividades_recentes(session),
        "desempenho_chart": desempenho_chart,
        "desempenho_eixo_y": eixo_y_ticks,
    }


@app.get("/ui/dashboard")
def ui_dashboard(
    request: Request, session: SessionDep, user: UIAdmin, mes: str | None = None
) -> HTMLResponse:
    ctx = {"user": user, **_ctx_dashboard(session, mes)}
    return templates.TemplateResponse(request, "dashboard.html", ctx)
