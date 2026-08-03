"""HTMX routes for perfis."""

from typing import Any

import structlog
from fastapi import Query, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListState
from xtreme_system.api.crud_ui.helpers import LIST_LIMIT_MAX, current_list_state
from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import (
    delete_conflict_detail,
    list_response,
    rollback_integrity_error_response,
    validation_error_detail,
    write_conflict_detail,
)
from xtreme_system.api.deps import SessionDep, UIAdmin, found, templates
from xtreme_system.api.setup import app
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Perfis (UI, admin) ----


def _parse_restricoes(form: Any) -> dict[str, dict[str, list[str]]]:
    restricoes: dict[str, dict[str, list[str]]] = {}
    for chave in form:
        if chave.startswith("oculto__"):
            _, pagina, campo = chave.split("__", 2)
            restricoes.setdefault(pagina, {}).setdefault("campos_ocultos", []).append(
                campo
            )
        elif chave.startswith("op__"):
            _, pagina, operacao = chave.split("__", 2)
            restricoes.setdefault(pagina, {}).setdefault("operacoes", []).append(
                operacao
            )
    return restricoes


def _perfis_response(
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
    todos = perfil.list_all(session)
    if state.sort == "nome":
        todos = sorted(
            todos,
            key=lambda item: _sort_key(item.nome),
            reverse=state.order == "desc",
        )
    perfis = todos[state.offset : state.offset + limit]
    return list_response(
        templates,
        request,
        template,
        user=user,
        list_key="perfis",
        lista=perfis,
        ctx_list={},
        sort=state.sort,
        order=state.order,
        limit=limit,
        offset=state.offset,
        erro=erro,
        status_code=status_code,
        success=success,
    )


@app.get("/ui/perfis")
def ui_perfis(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    sort: str = "",
    order: str = "asc",
    limit: int = Query(50, ge=1, le=LIST_LIMIT_MAX),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    state = ListState(sort=sort, order=order, limit=limit, offset=offset)
    template = (
        "_linhas_perfis.html" if request.headers.get("HX-Request") else "perfis.html"
    )
    return _perfis_response(request, session, user, template, state=state)


@app.get("/ui/perfis/novo")
def ui_perfil_novo(request: Request, _: UIAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_form_perfil.html",
        {"perfil": None, "paginas_disponiveis": perfil.PAGINAS},
    )


@app.get("/ui/perfis/{item_id}/editar")
def ui_perfil_editar(
    item_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = found(perfil.get(session, item_id), "Perfil")
    return templates.TemplateResponse(
        request,
        "_form_perfil.html",
        {"perfil": obj, "paginas_disponiveis": perfil.PAGINAS},
    )


@app.post("/ui/perfis")
async def ui_perfil_criar(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    form = await request.form()
    try:
        data = perfil.PerfilCreate(
            nome=str(form.get("nome", "")),
            paginas=form.getlist("paginas"),
            restricoes=_parse_restricoes(form),
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "_form_perfil.html",
            {
                "perfil": None,
                "paginas_disponiveis": perfil.PAGINAS,
                "erro": validation_error_detail(exc),
            },
            status_code=400,
        )
    try:
        perfil.create(session, data, user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: templates.TemplateResponse(
                request,
                "_form_perfil.html",
                {
                    "perfil": None,
                    "paginas_disponiveis": perfil.PAGINAS,
                    "erro": write_conflict_detail("Perfil"),
                },
                status_code=409,
            ),
        )
    return _perfis_response(request, session, user, "_perfis_ok.html", success=True)


@app.post("/ui/perfis/{item_id}")
async def ui_perfil_atualizar(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = found(perfil.get(session, item_id), "Perfil")
    form = await request.form()
    try:
        data = perfil.PerfilUpdate(
            nome=str(form.get("nome", "")),
            paginas=form.getlist("paginas"),
            restricoes=_parse_restricoes(form),
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "_form_perfil.html",
            {
                "perfil": obj,
                "paginas_disponiveis": perfil.PAGINAS,
                "erro": validation_error_detail(exc),
            },
            status_code=400,
        )
    try:
        perfil.update(session, obj, data, user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: templates.TemplateResponse(
                request,
                "_form_perfil.html",
                {
                    "perfil": obj,
                    "paginas_disponiveis": perfil.PAGINAS,
                    "erro": write_conflict_detail("Perfil"),
                },
                status_code=409,
            ),
        )
    return _perfis_response(request, session, user, "_perfis_ok.html", success=True)


@app.post("/ui/perfis/{item_id}/excluir")
def ui_perfil_excluir(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = found(perfil.get(session, item_id), "Perfil")
    try:
        perfil.delete(session, obj, user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: _perfis_response(
                request,
                session,
                user,
                "_linhas_perfis.html",
                erro=delete_conflict_detail(
                    "Perfil", "Perfil possui usuários vinculados"
                ),
                status_code=409,
            ),
        )
    return _perfis_response(request, session, user, "_linhas_perfis.html", success=True)
