"""HTMX routes for lancamentos de caixa por investidor."""

from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.responses import csv_response as _csv_response
from xtreme_system.api.crud_ui.responses import (
    error_response,
    ok_response,
    validation_error_detail,
)
from xtreme_system.api.deps import SessionDep, UIAdmin, UIUser, found, templates
from xtreme_system.api.setup import app
from xtreme_system.caixa import core as caixa
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.workflow.core import is_lancamento_automatico

_LANCAMENTO_SORT_FIELDS: dict[str, str] = {
    "data": "criado_em",
    "tipo": "tipo",
    "descricao": "descricao",
    "valor": "valor",
}


def _ctx_lancamentos(
    session: Session, investidor_id: int, sort: str = "", order: str = "asc"
) -> dict[str, Any]:
    query = caixa.query_by_investidor(session, investidor_id)
    field = _LANCAMENTO_SORT_FIELDS.get(sort, "id")
    col = getattr(caixa.LancamentoInvestimento, field)
    order_expr = col.desc() if order == "desc" else col.asc()
    lancamentos = list(query.order_by(order_expr).all())
    return {
        "investidor": found(investidor.get(session, investidor_id), "Investidor"),
        "lancamentos": lancamentos,
        "saldo": caixa.saldo(session, investidor_id),
        "sort": sort,
        "order": order,
    }


def _ok_lancamentos(
    request: Request, session: Session, user: usuario.Usuario, investidor_id: int
) -> HTMLResponse:
    ctx = _ctx_lancamentos(session, investidor_id)
    return ok_response(
        templates,
        request,
        "_lancamentos_ok.html",
        user=user,
        list_key="lancamentos",
        lista=ctx["lancamentos"],
        ctx_list={
            chave: valor for chave, valor in ctx.items() if chave != "lancamentos"
        },
    )


def _erro_lancamento(
    request: Request,
    investidor_id: int,
    exc: ValidationError | HTTPException,
    obj: caixa.LancamentoInvestimento | None,
) -> HTMLResponse:
    erro = (
        str(exc.detail)
        if isinstance(exc, HTTPException)
        else validation_error_detail(exc)
    )
    return error_response(
        templates,
        request,
        "_form_lancamento.html",
        ctx_form={
            "investidor_id": investidor_id,
            "tipos": list(caixa.TipoLancamento),
        },
        item_key="lancamento",
        item=obj,
        erro=erro,
        status_code=400,
    )


@app.get("/ui/investidores/{investidor_id}/lancamentos")
def ui_investidor_lancamentos(
    investidor_id: int,
    request: Request,
    session: SessionDep,
    user: UIUser,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    ctx = {
        "user": user,
        "investidor_id": investidor_id,
        **_ctx_lancamentos(session, investidor_id, sort, order),
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_linhas_lancamentos.html", ctx)
    return templates.TemplateResponse(request, "investidor_lancamentos.html", ctx)


@app.get("/ui/investidores/{investidor_id}/lancamentos/exportar")
def ui_investidor_lancamentos_exportar(
    investidor_id: int, session: SessionDep, _: UIUser
) -> Response:
    investidor_obj = found(investidor.get(session, investidor_id), "Investidor")
    lancamentos = caixa.list_by_investidor(session, investidor_id)
    return _csv_response(
        f"caixa-{investidor_obj.nome}.csv",
        ["Data", "Tipo", "Descricao", "Valor"],
        [
            [
                lanc.criado_em.isoformat(),
                lanc.tipo.value,
                lanc.descricao or "",
                f"{lanc.valor:.2f}",
            ]
            for lanc in lancamentos
        ],
    )


@app.get("/ui/investidores/{investidor_id}/lancamentos/novo")
def ui_lancamento_novo(
    investidor_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    found(investidor.get(session, investidor_id), "Investidor")
    return templates.TemplateResponse(
        request,
        "_form_lancamento.html",
        {
            "investidor_id": investidor_id,
            "lancamento": None,
            "tipos": list(caixa.TipoLancamento),
        },
    )


@app.get("/ui/investidores/{investidor_id}/lancamentos/{lancamento_id}/editar")
def ui_lancamento_editar(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    _: UIAdmin,
) -> HTMLResponse:
    obj = found(caixa.get(session, lancamento_id), "Lançamento")
    if is_lancamento_automatico(obj):
        raise HTTPException(
            status_code=403, detail="Editável apenas na tela de Veículos"
        )
    return templates.TemplateResponse(
        request,
        "_form_lancamento.html",
        {
            "investidor_id": investidor_id,
            "lancamento": obj,
            "tipos": list(caixa.TipoLancamento),
        },
    )


@app.post("/ui/investidores/{investidor_id}/lancamentos")
async def ui_lancamento_criar(
    investidor_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    found(investidor.get(session, investidor_id), "Investidor")
    form = await request.form()
    try:
        data = caixa.LancamentoInvestimentoCreate.model_validate(
            {**dict(form), "investidor_id": investidor_id}
        )
    except ValidationError as exc:
        return _erro_lancamento(request, investidor_id, exc, None)
    caixa.create(session, data, user.id)
    return _ok_lancamentos(request, session, user, investidor_id)


@app.post("/ui/investidores/{investidor_id}/lancamentos/{lancamento_id}")
async def ui_lancamento_atualizar(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = found(caixa.get(session, lancamento_id), "Lançamento")
    if is_lancamento_automatico(obj):
        raise HTTPException(
            status_code=403, detail="Editável apenas na tela de Veículos"
        )
    form = await request.form()
    try:
        data = caixa.LancamentoInvestimentoUpdate.model_validate(dict(form))
    except ValidationError as exc:
        return _erro_lancamento(request, investidor_id, exc, obj)
    caixa.update(session, obj, data, user.id)
    return _ok_lancamentos(request, session, user, investidor_id)


@app.post("/ui/investidores/{investidor_id}/lancamentos/{lancamento_id}/excluir")
def ui_lancamento_excluir(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = found(caixa.get(session, lancamento_id), "Lançamento")
    if is_lancamento_automatico(obj):
        raise HTTPException(
            status_code=403, detail="Exclusão apenas na tela de Veículos"
        )
    caixa.delete(session, obj, user.id)
    return templates.TemplateResponse(
        request,
        "_linhas_lancamentos.html",
        {
            "user": user,
            "investidor_id": investidor_id,
            **_ctx_lancamentos(session, investidor_id),
        },
    )
