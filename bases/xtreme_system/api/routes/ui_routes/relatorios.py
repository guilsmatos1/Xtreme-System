"""HTMX routes for relatórios (DRE por período)."""

from datetime import UTC, date, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

import structlog
from fastapi import Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.route_factories import _csv_response
from xtreme_system.api.routes.ui_routes.common import IdFiltro, PeriodoFiltro
from xtreme_system.api.setup import app
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- DRE por período (admin-only, a partir de fechamento_venda) ----

MESES_PADRAO = 11


class FiltroDre(PeriodoFiltro):
    investidor_id: IdFiltro = None
    vendedor_id: IdFiltro = None

    @classmethod
    def _periodo_padrao(cls) -> tuple[date, date]:
        hoje = datetime.now(UTC).date()
        total = hoje.year * 12 + hoje.month - 1 - MESES_PADRAO
        return date(total // 12, total % 12 + 1, 1), hoje


FiltroDreDep = Annotated[FiltroDre, Query()]


def _listar(session: Session, f: FiltroDre) -> list[fechamento_venda.FechamentoVenda]:
    data_de, data_ate = f.periodo
    return fechamento_venda.listar_para_dre(
        session,
        data_de=data_de,
        data_ate=data_ate,
        investidor_id=f.investidor_id,
        vendedor_id=f.vendedor_id,
    )


def _ctx_dre(session: Session, user: usuario.Usuario, f: FiltroDre) -> dict[str, Any]:
    data_de, data_ate = f.periodo
    fechamentos = _listar(session, f)
    filtros: dict[str, Any] = {
        "data_de": data_de.isoformat(),
        "data_ate": data_ate.isoformat(),
    }
    if f.investidor_id is not None:
        filtros["investidor_id"] = f.investidor_id
    if f.vendedor_id is not None:
        filtros["vendedor_id"] = f.vendedor_id
    return {
        "user": user,
        "titulo": "DRE",
        "fechamentos": fechamentos,
        "totais": fechamento_venda.dre_totais(fechamentos),
        "linhas_mes": fechamento_venda.dre_por_mes(fechamentos),
        "investidores": investidor.list_all(session),
        "vendedores": usuario.list_all(session),
        "f_data_de": data_de,
        "f_data_ate": data_ate,
        "f_investidor_id": f.investidor_id,
        "f_vendedor_id": f.vendedor_id,
        "filtros_qs": urlencode(filtros),
    }


@app.get("/ui/relatorios/dre")
def ui_relatorio_dre(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    filtros: FiltroDreDep,
) -> HTMLResponse:
    ctx = _ctx_dre(session, user, filtros)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_dre_resultado.html", ctx)
    return templates.TemplateResponse(request, "relatorios_dre.html", ctx)


@app.get("/ui/relatorios/dre/exportar")
def ui_relatorio_dre_exportar(
    session: SessionDep,
    _: UIAdmin,
    filtros: FiltroDreDep,
) -> Response:
    fechamentos = _listar(session, filtros)
    return _csv_response(
        "dre.csv",
        [
            "ID",
            "Data",
            "Venda",
            "Veiculo",
            "Placa",
            "Investidor",
            "Vendedor",
            "Receita",
            "Custo do veiculo",
            "Custos operacionais",
            "Debitos",
            "Lucro liquido",
        ],
        [
            [
                f.id,
                f.data_fechamento.isoformat(),
                f.venda_id,
                f.venda.veiculo.modelo,
                f.venda.veiculo.placa,
                f.venda.veiculo.investidor.nome,
                f.venda.vendedor.username if f.venda.vendedor else "",
                f.receita,
                f.custo_veiculo,
                f.custos_operacionais,
                f.debitos,
                f.lucro_liquido,
            ]
            for f in fechamentos
        ],
    )
