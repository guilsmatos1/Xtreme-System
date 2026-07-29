"""HTMX routes for auth."""

from typing import Annotated

import structlog
from fastapi import Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from xtreme_system.api.deps import SessionDep, templates
from xtreme_system.api.setup import app
from xtreme_system.auth import core as auth
from xtreme_system.empresa import core as empresa
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Login / logout ----


@app.get("/ui/login")
def ui_login_form(request: Request, session: SessionDep) -> HTMLResponse:
    config_empresa = empresa.get_config(session)
    return templates.TemplateResponse(
        request, "login.html", {"config_empresa": config_empresa}
    )


@app.post("/ui/login")
def ui_login(
    request: Request,
    session: SessionDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    user = usuario.get_by_username(session, username)
    if (
        user is None
        or not user.ativo
        or not auth.verify_password(password, user.senha_hash)
    ):
        config_empresa = empresa.get_config(session)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"erro": "Usuário ou senha inválidos", "config_empresa": config_empresa},
            status_code=401,
        )
    token = auth.create_access_token(user.username)
    resp = RedirectResponse("/ui/veiculos", status_code=303)
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=auth.get_settings().auth_token_expire_minutes * 60,
    )
    return resp


@app.post("/ui/logout")
def ui_logout() -> RedirectResponse:
    resp = RedirectResponse("/ui/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp
