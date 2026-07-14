"""HTMX routes for dashboard."""

from decimal import Decimal
from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.setup import app
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda

logger = structlog.get_logger(__name__)

# ---- Dashboard (KPIs, admin-only) ----


PERIODOS_DASHBOARD = {
    "30d": "30 dias",
    "90d": "90 dias",
    "12m": "12 meses",
}


def _ctx_dashboard(session: Session, periodo: str = "30d") -> dict[str, Any]:
    if periodo not in PERIODOS_DASHBOARD:
        periodo = "30d"

    resumo = veiculo.resumo_estoque(session)
    disponiveis, valor_estoque = resumo.get(
        veiculo.StatusVeiculo.disponivel, (0, Decimal("0"))
    )
    vendidos = resumo.get(veiculo.StatusVeiculo.vendido, (0, Decimal("0")))[0]
    total_avaliado = disponiveis + vendidos
    taxa_conversao = (vendidos / total_avaliado * 100) if total_avaliado else 0

    vendas_mes_count, vendas_mes_total = venda.resumo_mes(session)
    receita_tipo = venda.receita_por_tipo(session)
    funil = venda.funil_status(session)

    return {
        "titulo": "Dashboard",
        "periodo": periodo,
        "periodos": PERIODOS_DASHBOARD,
        "disponiveis": disponiveis,
        "vendidos": vendidos,
        "valor_estoque": valor_estoque,
        "taxa_conversao": taxa_conversao,
        "vendas_mes_count": vendas_mes_count,
        "vendas_mes_total": vendas_mes_total,
        "ticket_medio": venda.ticket_medio(session),
        "receita_tipo": [
            {
                "label": "Carros",
                "icone": "car",
                "valor": receita_tipo.get(veiculo.TipoVeiculo.carro, Decimal("0")),
            },
            {
                "label": "Motos",
                "icone": "bike",
                "valor": receita_tipo.get(veiculo.TipoVeiculo.moto, Decimal("0")),
            },
        ],
        "funil": [
            {
                "status": s.value,
                "count": funil.get(s, (0, Decimal("0")))[0],
                "valor": funil.get(s, (0, Decimal("0")))[1],
            }
            for s in venda.StatusVenda
        ],
        "ranking_vendedores": venda.ranking_vendedores(session),
        "tendencia_vendas": venda.tendencia_por_periodo(session, periodo),
        "tendencia_granularidade": "mês" if periodo == "12m" else "semana",
    }


@app.get("/ui/dashboard")
def ui_dashboard(
    request: Request, session: SessionDep, user: UIAdmin, periodo: str = "30d"
) -> HTMLResponse:
    ctx = {"user": user, **_ctx_dashboard(session, periodo)}
    return templates.TemplateResponse(request, "dashboard.html", ctx)
