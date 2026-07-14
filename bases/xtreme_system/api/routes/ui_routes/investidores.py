"""HTMX routes for investidores."""

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, UIUser, _found, templates
from xtreme_system.api.route_factories import _csv_response, _sort_key
from xtreme_system.api.setup import app
from xtreme_system.caixa import core as caixa
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Investidores + lançamentos de caixa (UI) ----


_LANCAMENTO_SORT_FIELDS: dict[str, str] = {
    "data": "criado_em",
    "tipo": "tipo",
    "descricao": "descricao",
    "valor": "valor",
}


def _ctx_lancamentos(
    session: Session, investidor_id: int, sort: str = "", order: str = "asc"
) -> dict[str, Any]:
    lancamentos = caixa.list_by_investidor(session, investidor_id)
    field = _LANCAMENTO_SORT_FIELDS.get(sort)
    if field:
        lancamentos = sorted(
            lancamentos,
            key=lambda lanc: _sort_key(getattr(lanc, field)),
            reverse=order == "desc",
        )
    return {
        "investidor": _found(investidor.get(session, investidor_id), "Investidor"),
        "lancamentos": lancamentos,
        "saldo": caixa.saldo(session, investidor_id),
        "sort": sort,
        "order": order,
    }


def _ok_lancamentos(
    request: Request, session: Session, user: usuario.Usuario, investidor_id: int
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_lancamentos_ok.html",
        {"user": user, **_ctx_lancamentos(session, investidor_id)},
    )


def _erro_lancamento(
    request: Request,
    investidor_id: int,
    exc: ValidationError | HTTPException,
    obj: caixa.LancamentoInvestimento | None,
) -> HTMLResponse:
    erro = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
    return templates.TemplateResponse(
        request,
        "_form_lancamento.html",
        {
            "investidor_id": investidor_id,
            "lancamento": obj,
            "tipos": list(caixa.TipoLancamento),
            "erro": erro,
        },
        status_code=400,
    )


def _ctx_investidores(
    session: Session, sort: str = "", order: str = "asc"
) -> dict[str, Any]:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_veiculos, valor_veiculos, total_aportado = caixa.agregados_investidores(session)
    reverse = order == "desc"
    if sort == "nome":
        investidores = sorted(
            investidores, key=lambda i: _sort_key(i.nome), reverse=reverse
        )
    elif sort == "saldo":
        investidores = sorted(
            investidores, key=lambda i: saldos.get(i.id, 0), reverse=reverse
        )
    elif sort == "num_veiculos":
        investidores = sorted(
            investidores, key=lambda i: num_veiculos.get(i.id, 0), reverse=reverse
        )
    elif sort == "valor_veiculos":
        investidores = sorted(
            investidores,
            key=lambda i: valor_veiculos.get(i.id, Decimal("0")),
            reverse=reverse,
        )
    elif sort == "total_investido":
        investidores = sorted(
            investidores,
            key=lambda i: total_aportado.get(i.id, Decimal("0")),
            reverse=reverse,
        )
    return {
        "titulo": "Investidores",
        "prefixo": "/ui/investidores",
        "itens": investidores,
        "saldos": saldos,
        "num_veiculos": num_veiculos,
        "valor_veiculos": valor_veiculos,
        "total_aportado": total_aportado,
        "sort": sort,
        "order": order,
    }


def _form_ctx_investidor(
    item: investidor.Investidor | None, erro: str | None = None
) -> dict[str, Any]:
    return {
        "titulo": "Investidores",
        "prefixo": "/ui/investidores",
        "item": item,
        "erro": erro,
    }


@app.get("/ui/investidores")
def ui_investidores(
    request: Request,
    session: SessionDep,
    user: UIUser,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    ctx = {"user": user, **_ctx_investidores(session, sort, order)}
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_linhas_investidores.html", ctx)
    return templates.TemplateResponse(request, "investidores.html", ctx)


@app.get("/ui/investidores/exportar")
def ui_investidores_exportar(session: SessionDep, _: UIUser) -> Response:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_v, val_v, tot_a = caixa.agregados_investidores(session)
    return _csv_response(
        "investidores.csv",
        ["Investidor", "Saldo", "N° Veículos", "Valor em Veículos", "Total Investido"],
        [
            [
                i.nome,
                f"{saldos.get(i.id, Decimal('0')):.2f}",
                num_v.get(i.id, 0),
                f"{val_v.get(i.id, Decimal('0')):.2f}",
                f"{tot_a.get(i.id, Decimal('0')):.2f}",
            ]
            for i in investidores
        ],
    )


@app.get("/ui/investidores/novo")
def ui_investidor_novo(request: Request, _: UIAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "_form_simples.html", _form_ctx_investidor(None)
    )


@app.get("/ui/investidores/{item_id}/editar")
def ui_investidor_editar(
    item_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = _found(investidor.get(session, item_id), "Investidores")
    return templates.TemplateResponse(
        request, "_form_simples.html", _form_ctx_investidor(obj)
    )


@app.post("/ui/investidores")
async def ui_investidor_criar(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    form = await request.form()
    nome = str(form.get("nome") or "").strip()
    if not nome:
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(None, "Nome obrigatório"),
            status_code=400,
        )
    try:
        obj = investidor.create(session, investidor.InvestidorCreate(nome=nome))
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(None, "Investidores já existe"),
            status_code=409,
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
        else:
            if aporte is not None:
                caixa.create(session, aporte)
    return templates.TemplateResponse(
        request, "_investidores_ok.html", {"user": user, **_ctx_investidores(session)}
    )


@app.post("/ui/investidores/{item_id}")
async def ui_investidor_atualizar(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = _found(investidor.get(session, item_id), "Investidores")
    nome = str((await request.form()).get("nome") or "").strip()
    if not nome:
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(obj, "Nome obrigatório"),
            status_code=400,
        )
    try:
        investidor.update(session, obj, investidor.InvestidorUpdate(nome=nome))
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(obj, "Investidores já existe"),
            status_code=409,
        )
    return templates.TemplateResponse(
        request, "_investidores_ok.html", {"user": user, **_ctx_investidores(session)}
    )


@app.post("/ui/investidores/{item_id}/excluir")
def ui_investidor_excluir(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = _found(investidor.get(session, item_id), "Investidores")
    if caixa.list_by_investidor(session, item_id):
        return templates.TemplateResponse(
            request,
            "_linhas_investidores.html",
            {
                "user": user,
                **_ctx_investidores(session),
                "msg": "Não é possível excluir investidor com lançamentos.",
            },
            status_code=409,
        )
    investidor.delete(session, obj)
    return templates.TemplateResponse(
        request,
        "_linhas_investidores.html",
        {"user": user, **_ctx_investidores(session)},
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
    investidor_obj = _found(investidor.get(session, investidor_id), "Investidor")
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
    _found(investidor.get(session, investidor_id), "Investidor")
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
    obj = _found(caixa.get(session, lancamento_id), "Lançamento")
    if obj.origem == caixa.OrigemLancamento.veiculo:
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
    _found(investidor.get(session, investidor_id), "Investidor")
    form = await request.form()
    try:
        data = caixa.LancamentoInvestimentoCreate.model_validate(
            {**dict(form), "investidor_id": investidor_id}
        )
    except ValidationError as exc:
        return _erro_lancamento(request, investidor_id, exc, None)
    caixa.create(session, data)
    return _ok_lancamentos(request, session, user, investidor_id)


@app.post("/ui/investidores/{investidor_id}/lancamentos/{lancamento_id}")
async def ui_lancamento_atualizar(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = _found(caixa.get(session, lancamento_id), "Lançamento")
    if obj.origem == caixa.OrigemLancamento.veiculo:
        raise HTTPException(
            status_code=403, detail="Editável apenas na tela de Veículos"
        )
    form = await request.form()
    try:
        data = caixa.LancamentoInvestimentoUpdate.model_validate(dict(form))
    except ValidationError as exc:
        return _erro_lancamento(request, investidor_id, exc, obj)
    caixa.update(session, obj, data)
    return _ok_lancamentos(request, session, user, investidor_id)


@app.post("/ui/investidores/{investidor_id}/lancamentos/{lancamento_id}/excluir")
def ui_lancamento_excluir(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = _found(caixa.get(session, lancamento_id), "Lançamento")
    if obj.origem == caixa.OrigemLancamento.veiculo:
        raise HTTPException(
            status_code=403, detail="Exclusão apenas na tela de Veículos"
        )
    caixa.delete(session, obj)
    return templates.TemplateResponse(
        request,
        "_linhas_lancamentos.html",
        {
            "user": user,
            "investidor_id": investidor_id,
            **_ctx_lancamentos(session, investidor_id),
        },
    )
