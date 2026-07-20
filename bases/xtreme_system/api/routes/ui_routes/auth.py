"""HTMX routes for auth."""

from typing import Annotated

import structlog
from fastapi import Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from xtreme_system.api.deps import SessionDep, templates
from xtreme_system.api.setup import _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS, _client_ip, app
from xtreme_system.auth import core as auth
from xtreme_system.auth.rate_limit import allow_login_attempt
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Login / logout ----


@app.get("/ui/login")
def ui_login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/ui/login")
def ui_login(
    request: Request,
    session: SessionDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    retry_after = allow_login_attempt(
        session, _client_ip(request), _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS
    )
    if retry_after is not None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"erro": "Muitas tentativas de login. Tente novamente em instantes."},
            status_code=429,
            headers={"Retry-After": str(int(retry_after))},
        )
    user = usuario.get_by_username(session, username)
    if (
        user is None
        or not user.ativo
        or not auth.verify_password(password, user.senha_hash)
    ):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"erro": "Usuário ou senha inválidos"},
            status_code=401,
        )
    token = auth.create_access_token(user.username, user.papel)
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
