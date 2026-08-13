"""HTMX routes for investidores."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated, cast

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListState
from xtreme_system.api.crud_ui.helpers import LIST_LIMIT_MAX, current_list_state
from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import csv_response as _csv_response
from xtreme_system.api.crud_ui.responses import (
    list_response,
    rollback_integrity_error_response,
    write_conflict_detail,
)
from xtreme_system.api.deps import (
    SessionDep,
    UIAdmin,
    UIUser,
    found,
    require_operacao,
    templates,
)
from xtreme_system.caixa import core as caixa
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)
router = APIRouter()


@dataclass(frozen=True)
class MetricasInvestidor:
    saldo: Decimal = Decimal("0")
    num_veiculos: int = 0
    valor_veiculos: Decimal = Decimal("0")
    total_aportado: Decimal = Decimal("0")


_METRICAS_INVESTIDOR_PADRAO = MetricasInvestidor()


def ordenar_investidores(
    investidores: list[investidor.Investidor],
    metricas: dict[int, MetricasInvestidor],
    sort: str,
    order: str,
) -> list[investidor.Investidor]:
    reverse = order == "desc"
    if sort == "nome":
        return sorted(
            investidores, key=lambda item: _sort_key(item.nome), reverse=reverse
        )
    if sort == "saldo":
        return sorted(
            investidores,
            key=lambda item: metricas.get(item.id, _METRICAS_INVESTIDOR_PADRAO).saldo,
            reverse=reverse,
        )
    if sort == "num_veiculos":
        return sorted(
            investidores,
            key=lambda item: (
                metricas.get(item.id, _METRICAS_INVESTIDOR_PADRAO).num_veiculos
            ),
            reverse=reverse,
        )
    if sort == "valor_veiculos":
        return sorted(
            investidores,
            key=lambda item: (
                metricas.get(item.id, _METRICAS_INVESTIDOR_PADRAO).valor_veiculos
            ),
            reverse=reverse,
        )
    if sort == "total_investido":
        return sorted(
            investidores,
            key=lambda item: (
                metricas.get(item.id, _METRICAS_INVESTIDOR_PADRAO).total_aportado
            ),
            reverse=reverse,
        )
    return investidores


def _ctx_investidores(
    session: Session, sort: str = "", order: str = "asc"
) -> dict[str, object]:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_veiculos, valor_veiculos, total_aportado = caixa.agregados_investidores(session)
    metricas = {
        item.id: MetricasInvestidor(
            saldo=saldos.get(item.id, Decimal("0")),
            num_veiculos=num_veiculos.get(item.id, 0),
            valor_veiculos=valor_veiculos.get(item.id, Decimal("0")),
            total_aportado=total_aportado.get(item.id, Decimal("0")),
        )
        for item in investidores
    }
    return {
        "titulo": "Investidores",
        "prefixo": "/ui/investidores",
        "itens": ordenar_investidores(investidores, metricas, sort, order),
        "saldos": saldos,
        "num_veiculos": num_veiculos,
        "valor_veiculos": valor_veiculos,
        "total_aportado": total_aportado,
        "sort": sort,
        "order": order,
    }


def _investidores_response(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    template: str,
    *,
    state: ListState | None = None,
    erro: str | None = None,
    status_code: int = 200,
    success: bool = False,
) -> HTMLResponse:
    state = state or current_list_state(request)
    limit = state.limit or 50
    context = _ctx_investidores(session, state.sort, state.order)
    todos = cast(list[investidor.Investidor], context.pop("itens"))
    context["total_investidores"] = len(todos)
    itens = todos[state.offset : state.offset + limit]
    return list_response(
        templates,
        request,
        template,
        user=user,
        list_key="itens",
        lista=itens,
        ctx_list=context,
        sort=state.sort,
        order=state.order,
        limit=limit,
        offset=state.offset,
        erro=erro,
        status_code=status_code,
        success=success,
    )


def _form_ctx_investidor(
    item: investidor.Investidor | None, erro: str | None = None
) -> dict[str, object]:
    return {
        "titulo": "Investidores",
        "prefixo": "/ui/investidores",
        "item": item,
        "erro": erro,
    }


@router.get("/ui/investidores")
def ui_investidores(
    request: Request,
    session: SessionDep,
    user: UIUser,
    sort: str = "",
    order: str = "asc",
    limit: int = Query(50, ge=1, le=LIST_LIMIT_MAX),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    state = ListState(sort=sort, order=order, limit=limit, offset=offset)
    template = (
        "_linhas_investidores.html"
        if request.headers.get("HX-Request")
        else "investidores.html"
    )
    return _investidores_response(request, session, user, template, state=state)


@router.get("/ui/investidores/exportar")
def ui_investidores_exportar(
    session: SessionDep,
    _: Annotated[
        usuario.Usuario, Depends(require_operacao("investidores", "exportar"))
    ],
) -> Response:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_v, val_v, tot_a = caixa.agregados_investidores(session)
    return _csv_response(
        "investidores.csv",
        ["Investidor", "Saldo", "N° Veículos", "Valor em Veículos", "Total Investido"],
        [
            [
                item.nome,
                f"{saldos.get(item.id, Decimal('0')):.2f}",
                num_v.get(item.id, 0),
                f"{val_v.get(item.id, Decimal('0')):.2f}",
                f"{tot_a.get(item.id, Decimal('0')):.2f}",
            ]
            for item in investidores
        ],
    )


@router.get("/ui/investidores/novo")
def ui_investidor_novo(request: Request, _: UIAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "_form_simples.html", _form_ctx_investidor(None)
    )


_EditarInvestidorDep = Annotated[
    usuario.Usuario, Depends(require_operacao("investidores", "editar"))
]
_ExcluirInvestidorDep = Annotated[
    usuario.Usuario, Depends(require_operacao("investidores", "excluir"))
]


@router.get("/ui/investidores/{item_id}/editar")
def ui_investidor_editar(
    item_id: int, request: Request, session: SessionDep, _: _EditarInvestidorDep
) -> HTMLResponse:
    obj = found(investidor.get(session, item_id), "Investidores")
    return templates.TemplateResponse(
        request, "_form_simples.html", _form_ctx_investidor(obj)
    )


@router.post("/ui/investidores")
async def ui_investidor_criar(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    form = await request.form()
    nome = str(form.get("nome") or "").strip().upper()
    if not nome:
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(None, "Nome obrigatório"),
            status_code=400,
        )
    try:
        obj = investidor.create(
            session, investidor.InvestidorCreate(nome=nome), user.id
        )
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx_investidor(None, write_conflict_detail("Investidor")),
                status_code=409,
            ),
        )
    valor_str = str(form.get("valor_investido") or "").strip()
    if valor_str:
        try:
            valor = Decimal(valor_str.replace(",", "."))
            aporte = (
                caixa.LancamentoInvestimentoCreate(
                    investidor_id=obj.id,
                    tipo=caixa.TipoLancamento.aporte,
                    valor=valor,
                    descricao="Aporte inicial",
                )
                if valor > 0
                else None
            )
        except (InvalidOperation, ValidationError):
            logger.warning(
                "aporte_inicial_invalido", investidor_id=obj.id, valor_str=valor_str
            )
            session.rollback()
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx_investidor(None, "Valor investido inválido"),
                status_code=400,
            )
        if aporte is not None:
            caixa.create(session, aporte, user.id)
    return _investidores_response(
        request, session, user, "_investidores_ok.html", success=True
    )


@router.post("/ui/investidores/{item_id}")
async def ui_investidor_atualizar(
    item_id: int, request: Request, session: SessionDep, user: _EditarInvestidorDep
) -> HTMLResponse:
    obj = found(investidor.get(session, item_id), "Investidores")
    nome = str((await request.form()).get("nome") or "").strip()
    if not nome:
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(obj, "Nome obrigatório"),
            status_code=400,
        )
    try:
        investidor.update(session, obj, investidor.InvestidorUpdate(nome=nome), user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx_investidor(obj, write_conflict_detail("Investidor")),
                status_code=409,
            ),
        )
    return _investidores_response(
        request, session, user, "_investidores_ok.html", success=True
    )


@router.post("/ui/investidores/{item_id}/excluir")
def ui_investidor_excluir(
    item_id: int, request: Request, session: SessionDep, user: _ExcluirInvestidorDep
) -> HTMLResponse:
    obj = found(investidor.get(session, item_id), "Investidores")
    if caixa.list_by_investidor(session, item_id):
        return _investidores_response(
            request,
            session,
            user,
            "_linhas_investidores.html",
            erro="Não é possível excluir investidor com lançamentos.",
            status_code=409,
        )
    investidor.delete(session, obj, user.id)
    return _investidores_response(
        request, session, user, "_linhas_investidores.html", success=True
    )
