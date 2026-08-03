"""HTMX routes for conta (perfil do usuário logado)."""

from typing import Annotated

from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from xtreme_system.api.deps import SessionDep, UIUser, templates
from xtreme_system.api.setup import app
from xtreme_system.auth import core as auth
from xtreme_system.usuario import core as usuario

# ---- Conta (autoatendimento, qualquer usuário autenticado) ----


@app.get("/ui/conta")
def ui_conta(request: Request, user: UIUser) -> HTMLResponse:
    return templates.TemplateResponse(request, "conta.html", {"user": user})


@app.post("/ui/conta/senha")
def ui_conta_senha_alterar(
    request: Request,
    session: SessionDep,
    user: UIUser,
    senha_atual: Annotated[str, Form()],
    nova_senha: Annotated[str, Form()],
    confirmar_senha: Annotated[str, Form()],
) -> HTMLResponse:
    if not auth.verify_password(senha_atual, user.senha_hash):
        return templates.TemplateResponse(
            request,
            "conta.html",
            {"user": user, "erro": "Senha atual incorreta"},
            status_code=400,
        )
    if nova_senha != confirmar_senha:
        return templates.TemplateResponse(
            request,
            "conta.html",
            {"user": user, "erro": "A confirmação não coincide com a nova senha"},
            status_code=400,
        )
    try:
        usuario.change_password(session, user, nova_senha)
    except usuario.SenhaFracaError as exc:
        return templates.TemplateResponse(
            request,
            "conta.html",
            {"user": user, "erro": str(exc)},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "conta.html", {"user": user, "sucesso": "Senha alterada com sucesso."}
    )
