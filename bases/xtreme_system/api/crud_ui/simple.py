from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import CrudModule
from xtreme_system.api.crud_ui.query import sort_key
from xtreme_system.api.crud_ui.responses import (
    csv_response,
    delete_conflict_detail,
    rollback_integrity_error_response,
    success_response,
    write_conflict_detail,
)
from xtreme_system.api.deps import SessionDep, UIAdmin, UIUser, _found
from xtreme_system.usuario import core as usuario


def register_ui_simples(
    app: FastAPI,
    templates: Jinja2Templates,
    ui_prefix: str,
    titulo: str,
    module: CrudModule[Any, Any, Any],
    create_schema: type,
    update_schema: type,
    export_filename: str,
) -> None:
    def _ctx(
        user: usuario.Usuario,
        session: Session,
        sort: str = "",
        order: str = "asc",
        **extra: Any,
    ) -> dict[str, Any]:
        itens = module.list_all(session)
        if sort == "nome":
            itens = sorted(
                itens, key=lambda item: sort_key(item.nome), reverse=order == "desc"
            )
        return {
            "user": user,
            "titulo": titulo,
            "prefixo": ui_prefix,
            "itens": itens,
            "sort": sort,
            "order": order,
            **extra,
        }

    def _form_ctx(item: Any, erro: str | None = None) -> dict[str, Any]:
        return {"titulo": titulo, "prefixo": ui_prefix, "item": item, "erro": erro}

    async def _nome(request: Request) -> str:
        return str((await request.form()).get("nome") or "").strip()

    @app.get(ui_prefix)
    def _lista(
        request: Request,
        session: SessionDep,
        user: UIUser,
        sort: str = "",
        order: str = "asc",
    ) -> HTMLResponse:
        ctx = _ctx(user, session, sort, order)
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(request, "_linhas_simples.html", ctx)
        return templates.TemplateResponse(request, "simples.html", ctx)

    @app.get(f"{ui_prefix}/exportar")
    def _exportar(session: SessionDep, _: UIUser) -> Response:
        itens = module.list_all(session)
        return csv_response(
            export_filename,
            ["ID", "Nome"],
            [[item.id, item.nome] for item in itens],
        )

    @app.get(f"{ui_prefix}/novo")
    def _novo(request: Request, _: UIAdmin) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "_form_simples.html", _form_ctx(None)
        )

    @app.get(f"{ui_prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int, request: Request, session: SessionDep, _: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        return templates.TemplateResponse(request, "_form_simples.html", _form_ctx(obj))

    @app.post(ui_prefix)
    async def _criar(
        request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        nome = await _nome(request)
        if not nome:
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(None, "Nome obrigatório"),
                status_code=400,
            )
        try:
            module.create(session, create_schema(nome=nome), user.id)
        except IntegrityError:
            return rollback_integrity_error_response(
                session,
                lambda: templates.TemplateResponse(
                    request,
                    "_form_simples.html",
                    _form_ctx(None, write_conflict_detail(titulo)),
                    status_code=409,
                ),
            )
        return success_response(
            templates, request, "_simples_ok.html", _ctx(user, session)
        )

    @app.post(f"{ui_prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        nome = await _nome(request)
        if not nome:
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(obj, "Nome obrigatório"),
                status_code=400,
            )
        try:
            module.update(session, obj, update_schema(nome=nome), user.id)
        except IntegrityError:
            return rollback_integrity_error_response(
                session,
                lambda: templates.TemplateResponse(
                    request,
                    "_form_simples.html",
                    _form_ctx(obj, write_conflict_detail(titulo)),
                    status_code=409,
                ),
            )
        return success_response(
            templates, request, "_simples_ok.html", _ctx(user, session)
        )

    @app.post(f"{ui_prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        msg = None
        try:
            module.delete(session, obj, user.id)
        except IntegrityError:
            return rollback_integrity_error_response(
                session,
                lambda: templates.TemplateResponse(
                    request,
                    "_linhas_simples.html",
                    _ctx(user, session, msg=delete_conflict_detail(titulo)),
                ),
            )
        return success_response(
            templates, request, "_linhas_simples.html", _ctx(user, session, msg=msg)
        )
