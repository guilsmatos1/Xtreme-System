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


def _ctx_dashboard(session: Session) -> dict[str, Any]:
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
    }


@app.get("/ui/dashboard")
def ui_dashboard(request: Request, session: SessionDep, user: UIAdmin) -> HTMLResponse:
    ctx = {"user": user, **_ctx_dashboard(session)}
    return templates.TemplateResponse(request, "dashboard.html", ctx)
