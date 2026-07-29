"""HTMX routes for usuarios."""

from typing import Annotated, Any

import structlog
from fastapi import Form, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import csv_response as _csv_response
from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.setup import app
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Usuários (UI, admin) ----


_USUARIO_SORT_FIELDS: dict[str, str] = {
    "id": "id",
    "username": "username",
    "nome": "nome",
    "papel": "papel",
    "ativo": "ativo",
}


def _usuarios_ctx(
    session: Session, user: usuario.Usuario, **extra: Any
) -> dict[str, Any]:
    return {
        "user": user,
        "usuarios": usuario.list_all(session),
        "perfis": perfil.list_all(session),
        "sort": "",
        "order": "asc",
        "oob": True,
        **extra,
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
    ctx = {
        "user": user,
        "usuarios": usuarios,
        "perfis": perfil.list_all(session),
        "sort": sort,
        "order": order,
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_linhas_usuarios.html", ctx)
    return templates.TemplateResponse(request, "usuarios.html", ctx)


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
    if usuario.get_by_username(session, username) is not None:
        return templates.TemplateResponse(
            request,
            "_form_usuario.html",
            {"perfis": perfil.list_all(session), "erro": "username já existe"},
            status_code=400,
        )
    if perfil_id is not None and perfil.get(session, perfil_id) is None:
        return templates.TemplateResponse(
            request,
            "_form_usuario.html",
            {"perfis": perfil.list_all(session), "erro": "perfil não encontrado"},
            status_code=400,
        )
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
    except usuario.SenhaFracaError as exc:
        return templates.TemplateResponse(
            request,
            "_form_usuario.html",
            {"perfis": perfil.list_all(session), "erro": str(exc)},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "_usuarios_ok.html", _usuarios_ctx(session, user)
    )


@app.post("/ui/usuarios/{user_id}/excluir")
def ui_usuario_excluir(
    user_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    if user_id == user.id:
        return templates.TemplateResponse(
            request,
            "usuarios.html",
            _usuarios_ctx(session, user, erro="não pode excluir a si mesmo"),
            status_code=400,
        )
    obj = _found(usuario.get(session, user_id), "Usuário")
    usuario.delete(session, obj, user.id)
    return templates.TemplateResponse(
        request, "_linhas_usuarios.html", _usuarios_ctx(session, user)
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
    try:
        usuario.change_password(session, obj, nova_senha, user.id)
    except usuario.SenhaFracaError as exc:
        return templates.TemplateResponse(
            request,
            "_form_senha.html",
            {"usuario": obj, "erro": str(exc)},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "_linhas_usuarios.html", _usuarios_ctx(session, user)
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
    return templates.TemplateResponse(
        request, "_linhas_usuarios.html", _usuarios_ctx(session, user)
    )


@app.get("/ui/usuarios/{user_id}/editar")
def ui_usuario_editar_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = _found(usuario.get(session, user_id), "Usuário")
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
    obj = _found(usuario.get(session, user_id), "Usuário")
    if (
        username != obj.username
        and usuario.get_by_username(session, username) is not None
    ):
        return templates.TemplateResponse(
            request,
            "_form_usuario_editar.html",
            {
                "usuario": obj,
                "perfis": perfil.list_all(session),
                "erro": "username já existe",
            },
            status_code=400,
        )
    if perfil_id is not None and perfil.get(session, perfil_id) is None:
        return templates.TemplateResponse(
            request,
            "_form_usuario_editar.html",
            {
                "usuario": obj,
                "perfis": perfil.list_all(session),
                "erro": "perfil não encontrado",
            },
            status_code=400,
        )
    usuario.update(
        session,
        obj,
        usuario.UsuarioUpdate(
            username=username, nome=nome, papel=papel, ativo=ativo, perfil_id=perfil_id
        ),
        user.id,
    )
    if senha:
        try:
            usuario.change_password(session, obj, senha, user.id)
        except usuario.SenhaFracaError as exc:
            return templates.TemplateResponse(
                request,
                "_form_usuario_editar.html",
                {"usuario": obj, "perfis": perfil.list_all(session), "erro": str(exc)},
                status_code=400,
            )
    return templates.TemplateResponse(
        request, "_linhas_usuarios.html", _usuarios_ctx(session, user)
    )
