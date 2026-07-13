"""HTMX routes for usuarios."""

from typing import Annotated

import structlog
from fastapi import Form, Request, Response
from fastapi.responses import HTMLResponse

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import _csv_response, _sort_key
from xtreme_system.api.setup import app
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Usuários (UI, admin) ----


_USUARIO_SORT_FIELDS: dict[str, str] = {
    "id": "id",
    "username": "username",
    "papel": "papel",
    "ativo": "ativo",
}


@app.get("/ui/usuarios")
def ui_usuarios(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    usuarios = usuario.list_all(session)
    field = _USUARIO_SORT_FIELDS.get(sort)
    if field:
        usuarios = sorted(
            usuarios,
            key=lambda u: _sort_key(getattr(u, field)),
            reverse=order == "desc",
        )
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuarios,
            "perfis": perfil.list_all(session),
            "sort": sort,
            "order": order,
        },
    )


@app.get("/ui/usuarios/exportar")
def ui_usuarios_exportar(session: SessionDep, _: UIAdmin) -> Response:
    usuarios = usuario.list_all(session)
    return _csv_response(
        "usuarios.csv",
        ["ID", "Usuario", "Papel", "Ativo"],
        [
            [u.id, u.username, u.papel.value, "sim" if u.ativo else "nao"]
            for u in usuarios
        ],
    )


@app.post("/ui/usuarios")
def ui_usuario_criar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    username: Annotated[str, Form()],
    senha: Annotated[str, Form()],
    papel: Annotated[usuario.Papel, Form()] = usuario.Papel.vendedor,
    perfil_id: Annotated[int | None, Form()] = None,
) -> HTMLResponse:
    erro = None
    if usuario.get_by_username(session, username) is not None:
        erro = "username já existe"
    else:
        session.info["usuario_id"] = user.id
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username=username, senha=senha, papel=papel, perfil_id=perfil_id
            ),
        )
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuario.list_all(session),
            "perfis": perfil.list_all(session),
            "erro": erro,
        },
        status_code=400 if erro else 200,
    )


@app.post("/ui/usuarios/{user_id}/excluir")
def ui_usuario_excluir(
    user_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    if user_id == user.id:
        return templates.TemplateResponse(
            request,
            "usuarios.html",
            {
                "user": user,
                "usuarios": usuario.list_all(session),
                "perfis": perfil.list_all(session),
                "erro": "não pode excluir a si mesmo",
            },
            status_code=400,
        )
    obj = _found(usuario.get(session, user_id), "Usuário")
    session.info["usuario_id"] = user.id
    usuario.delete(session, obj)
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuario.list_all(session),
            "perfis": perfil.list_all(session),
            "sort": "",
            "order": "asc",
        },
    )


@app.get("/ui/usuarios/{user_id}/senha")
def ui_usuario_senha_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = _found(usuario.get(session, user_id), "Usuário")
    return templates.TemplateResponse(request, "_form_senha.html", {"usuario": obj})


@app.post("/ui/usuarios/{user_id}/senha")
def ui_usuario_senha_alterar(
    user_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    nova_senha: Annotated[str, Form()],
) -> HTMLResponse:
    obj = _found(usuario.get(session, user_id), "Usuário")
    session.info["usuario_id"] = user.id
    usuario.change_password(session, obj, nova_senha)
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuario.list_all(session),
            "perfis": perfil.list_all(session),
            "sort": "",
            "order": "asc",
        },
    )


@app.get("/ui/usuarios/{user_id}/perfil")
def ui_usuario_perfil_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = _found(usuario.get(session, user_id), "Usuário")
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
    obj = _found(usuario.get(session, user_id), "Usuário")
    session.info["usuario_id"] = user.id
    usuario.set_perfil(session, obj, perfil_id)
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuario.list_all(session),
            "perfis": perfil.list_all(session),
            "sort": "",
            "order": "asc",
        },
    )
