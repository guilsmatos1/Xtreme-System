"""HTMX routes for usuarios."""

from typing import Annotated

from fastapi import Form, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListState
from xtreme_system.api.crud_ui.helpers import LIST_LIMIT_MAX, current_list_state
from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import csv_response as _csv_response
from xtreme_system.api.crud_ui.responses import list_response
from xtreme_system.api.deps import SessionDep, UIAdmin, found, templates
from xtreme_system.api.setup import app
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

# ---- Usuários (UI, admin) ----


_USUARIO_SORT_FIELDS: dict[str, str] = {
    "id": "id",
    "username": "username",
    "nome": "nome",
    "papel": "papel",
    "ativo": "ativo",
}


def _usuarios_stats(usuarios: list[usuario.Usuario]) -> dict[str, int]:
    admins = sum(item.papel == usuario.Papel.admin for item in usuarios)
    ativos = sum(item.ativo for item in usuarios)
    return {
        "total_usuarios": len(usuarios),
        "total_usuarios_ativos": ativos,
        "total_usuarios_admins": admins,
        "total_usuarios_funcionarios": len(usuarios) - admins,
    }


def _usuarios_response(
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
    todos = usuario.list_all(session)
    field = _USUARIO_SORT_FIELDS.get(state.sort)
    if field:
        todos = sorted(
            todos,
            key=lambda item: _sort_key(getattr(item, field)),
            reverse=state.order == "desc",
        )
    usuarios = todos[state.offset : state.offset + limit]
    return list_response(
        templates,
        request,
        template,
        user=user,
        list_key="usuarios",
        lista=usuarios,
        ctx_list={
            "perfis": perfil.list_all(session),
            **_usuarios_stats(todos),
        },
        sort=state.sort,
        order=state.order,
        limit=limit,
        offset=state.offset,
        erro=erro,
        status_code=status_code,
        success=success,
    )


@app.get("/ui/usuarios")
def ui_usuarios(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    sort: str = "",
    order: str = "asc",
    limit: Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HTMLResponse:
    state = ListState(sort=sort, order=order, limit=limit, offset=offset)
    template = (
        "_linhas_usuarios.html"
        if request.headers.get("HX-Request")
        else "usuarios.html"
    )
    return _usuarios_response(request, session, user, template, state=state)


@app.get("/ui/usuarios/exportar")
def ui_usuarios_exportar(session: SessionDep, _: UIAdmin) -> Response:
    usuarios = usuario.list_all(session)
    return _csv_response(
        "usuarios.csv",
        ["ID", "Usuario", "Nome", "Papel", "Ativo"],
        [
            [u.id, u.username, u.nome or "", u.papel.value, "sim" if u.ativo else "nao"]
            for u in usuarios
        ],
    )


@app.get("/ui/usuarios/novo")
def ui_usuario_novo(request: Request, session: SessionDep, _: UIAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "_form_usuario.html", {"perfis": perfil.list_all(session)}
    )


@app.post("/ui/usuarios")
def ui_usuario_criar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    username: Annotated[str, Form()],
    senha: Annotated[str, Form()],
    nome: Annotated[str | None, Form()] = None,
    papel: Annotated[usuario.Papel, Form()] = usuario.Papel.funcionario,
    perfil_id: Annotated[int | None, Form()] = None,
) -> HTMLResponse:
    try:
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username=username,
                nome=nome,
                senha=senha,
                papel=papel,
                perfil_id=perfil_id,
            ),
            user.id,
        )
    except (usuario.SenhaFracaError, usuario.UsuarioValidationError) as exc:
        return templates.TemplateResponse(
            request,
            "_form_usuario.html",
            {"perfis": perfil.list_all(session), "erro": str(exc)},
            status_code=400,
        )
    return _usuarios_response(request, session, user, "_usuarios_ok.html", success=True)


@app.post("/ui/usuarios/{user_id}/excluir")
def ui_usuario_excluir(
    user_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    if user_id == user.id:
        template = (
            "_linhas_usuarios.html"
            if request.headers.get("HX-Request")
            else "usuarios.html"
        )
        return _usuarios_response(
            request,
            session,
            user,
            template,
            erro="não pode excluir a si mesmo",
            status_code=400,
        )
    obj = found(usuario.get(session, user_id), "Usuário")
    usuario.delete(session, obj, user.id)
    return _usuarios_response(
        request, session, user, "_linhas_usuarios.html", success=True
    )


@app.get("/ui/usuarios/{user_id}/senha")
def ui_usuario_senha_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = found(usuario.get(session, user_id), "Usuário")
    return templates.TemplateResponse(request, "_form_senha.html", {"usuario": obj})


@app.post("/ui/usuarios/{user_id}/senha")
def ui_usuario_senha_alterar(
    user_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    nova_senha: Annotated[str, Form()],
) -> HTMLResponse:
    obj = found(usuario.get(session, user_id), "Usuário")
    try:
        usuario.change_password(session, obj, nova_senha, user.id)
    except usuario.SenhaFracaError as exc:
        return templates.TemplateResponse(
            request,
            "_form_senha.html",
            {"usuario": obj, "erro": str(exc)},
            status_code=400,
        )
    return _usuarios_response(
        request, session, user, "_linhas_usuarios.html", success=True
    )


@app.get("/ui/usuarios/{user_id}/perfil")
def ui_usuario_perfil_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = found(usuario.get(session, user_id), "Usuário")
    return templates.TemplateResponse(
        request,
        "_form_perfil_usuario.html",
        {"usuario": obj, "perfis": perfil.list_all(session)},
    )


@app.post("/ui/usuarios/{user_id}/perfil")
def ui_usuario_perfil_alterar(
    user_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    perfil_id: Annotated[int | None, Form()] = None,
) -> HTMLResponse:
    obj = found(usuario.get(session, user_id), "Usuário")
    if perfil_id is not None and perfil.get(session, perfil_id) is None:
        return templates.TemplateResponse(
            request,
            "_form_perfil_usuario.html",
            {
                "usuario": obj,
                "perfis": perfil.list_all(session),
                "erro": "Perfil inválido",
            },
            status_code=400,
        )
    usuario.set_perfil(session, obj, perfil_id, user.id)
    return _usuarios_response(
        request, session, user, "_linhas_usuarios.html", success=True
    )


@app.get("/ui/usuarios/{user_id}/editar")
def ui_usuario_editar_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = found(usuario.get(session, user_id), "Usuário")
    return templates.TemplateResponse(
        request,
        "_form_usuario_editar.html",
        {"usuario": obj, "perfis": perfil.list_all(session)},
    )


@app.post("/ui/usuarios/{user_id}/editar")
def ui_usuario_editar(
    user_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    username: Annotated[str, Form()],
    senha: Annotated[str | None, Form()] = None,
    nome: Annotated[str | None, Form()] = None,
    papel: Annotated[usuario.Papel, Form()] = usuario.Papel.funcionario,
    ativo: Annotated[bool, Form()] = True,
    perfil_id: Annotated[int | None, Form()] = None,
) -> HTMLResponse:
    obj = found(usuario.get(session, user_id), "Usuário")
    try:
        if senha:
            usuario.validate_senha(senha)
        usuario.update(
            session,
            obj,
            usuario.UsuarioUpdate(
                username=username,
                nome=nome,
                papel=papel,
                ativo=ativo,
                perfil_id=perfil_id,
            ),
            user.id,
        )
        if senha:
            usuario.change_password(session, obj, senha, user.id)
    except (usuario.SenhaFracaError, usuario.UsuarioValidationError) as exc:
        return templates.TemplateResponse(
            request,
            "_form_usuario_editar.html",
            {"usuario": obj, "perfis": perfil.list_all(session), "erro": str(exc)},
            status_code=400,
        )
    return _usuarios_response(
        request, session, user, "_linhas_usuarios.html", success=True
    )
