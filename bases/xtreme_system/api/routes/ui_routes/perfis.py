"""HTMX routes for perfis."""

from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import _sort_key
from xtreme_system.api.setup import app
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Perfis (UI, admin) ----


def _perfis_ctx(
    session: Session, user: usuario.Usuario, **extra: Any
) -> dict[str, Any]:
    return {
        "user": user,
        "perfis": perfil.list_all(session),
        "sort": "",
        "order": "asc",
        **extra,
    }


@app.get("/ui/perfis")
def ui_perfis(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    perfis = perfil.list_all(session)
    if sort == "nome":
        perfis = sorted(
            perfis, key=lambda p: _sort_key(p.nome), reverse=order == "desc"
        )
    return templates.TemplateResponse(
        request,
        "perfis.html",
        {"user": user, "perfis": perfis, "sort": sort, "order": order},
    )


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
    obj = _found(perfil.get(session, item_id), "Perfil")
    return templates.TemplateResponse(
        request,
        "_form_perfil.html",
        {"perfil": obj, "paginas_disponiveis": perfil.PAGINAS},
    )


@app.post("/ui/perfis")
async def ui_perfil_criar(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    form = await request.form()
    try:
        data = perfil.PerfilCreate(
            nome=str(form.get("nome", "")), paginas=form.getlist("paginas")
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "_form_perfil.html",
            {
                "perfil": None,
                "paginas_disponiveis": perfil.PAGINAS,
                "erro": "Dados inválidos",
            },
            status_code=400,
        )
    try:
        perfil.create(session, data)
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "_form_perfil.html",
            {
                "perfil": None,
                "paginas_disponiveis": perfil.PAGINAS,
                "erro": "Perfil já existe",
            },
            status_code=409,
        )
    return templates.TemplateResponse(
        request, "_perfis_ok.html", _perfis_ctx(session, user)
    )


@app.post("/ui/perfis/{item_id}")
async def ui_perfil_atualizar(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    obj = _found(perfil.get(session, item_id), "Perfil")
    form = await request.form()
    data = perfil.PerfilUpdate(
        nome=str(form.get("nome", "")), paginas=form.getlist("paginas")
    )
    try:
        perfil.update(session, obj, data)
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "_form_perfil.html",
            {
                "perfil": obj,
                "paginas_disponiveis": perfil.PAGINAS,
                "erro": "Perfil já existe",
            },
            status_code=409,
        )
    return templates.TemplateResponse(
        request, "_perfis_ok.html", _perfis_ctx(session, user)
    )


@app.post("/ui/perfis/{item_id}/excluir")
def ui_perfil_excluir(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    obj = _found(perfil.get(session, item_id), "Perfil")
    try:
        perfil.delete(session, obj)
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "_linhas_perfis.html",
            {**_perfis_ctx(session, user), "msg": "Perfil possui usuários vinculados"},
            status_code=409,
        )
    return templates.TemplateResponse(
        request, "_linhas_perfis.html", _perfis_ctx(session, user)
    )
