"""HTMX routes for investidores."""

from decimal import Decimal, InvalidOperation

import structlog
from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, UIUser, _found, templates
from xtreme_system.api.route_factories import _csv_response, _sort_key
from xtreme_system.api.setup import app
from xtreme_system.caixa import core as caixa
from xtreme_system.investidor import core as investidor

logger = structlog.get_logger(__name__)


def ordenar_investidores(
    investidores: list[investidor.Investidor],
    saldos: dict[int, Decimal],
    num_veiculos: dict[int, int],
    valor_veiculos: dict[int, Decimal],
    total_aportado: dict[int, Decimal],
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
            investidores, key=lambda item: saldos.get(item.id, 0), reverse=reverse
        )
    if sort == "num_veiculos":
        return sorted(
            investidores,
            key=lambda item: num_veiculos.get(item.id, 0),
            reverse=reverse,
        )
    if sort == "valor_veiculos":
        return sorted(
            investidores,
            key=lambda item: valor_veiculos.get(item.id, Decimal("0")),
            reverse=reverse,
        )
    if sort == "total_investido":
        return sorted(
            investidores,
            key=lambda item: total_aportado.get(item.id, Decimal("0")),
            reverse=reverse,
        )
    return investidores


def _ctx_investidores(
    session: Session, sort: str = "", order: str = "asc"
) -> dict[str, object]:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_veiculos, valor_veiculos, total_aportado = caixa.agregados_investidores(session)
    return {
        "titulo": "Investidores",
        "prefixo": "/ui/investidores",
        "itens": ordenar_investidores(
            investidores,
            saldos,
            num_veiculos,
            valor_veiculos,
            total_aportado,
            sort,
            order,
        ),
        "saldos": saldos,
        "num_veiculos": num_veiculos,
        "valor_veiculos": valor_veiculos,
        "total_aportado": total_aportado,
        "sort": sort,
        "order": order,
    }


def _form_ctx_investidor(
    item: investidor.Investidor | None, erro: str | None = None
) -> dict[str, object]:
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
                item.nome,
                f"{saldos.get(item.id, Decimal('0')):.2f}",
                num_v.get(item.id, 0),
                f"{val_v.get(item.id, Decimal('0')):.2f}",
                f"{tot_a.get(item.id, Decimal('0')):.2f}",
            ]
            for item in investidores
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
