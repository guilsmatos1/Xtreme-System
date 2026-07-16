"""HTMX routes for conta do usuario logado."""

from typing import Annotated

from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from xtreme_system.api.deps import SessionDep, UIUser, templates
from xtreme_system.api.setup import app
from xtreme_system.auth import core as auth
from xtreme_system.usuario import core as usuario


@app.get("/ui/conta")
def ui_conta(request: Request, user: UIUser) -> HTMLResponse:
    return templates.TemplateResponse(request, "conta.html", {"user": user})


@app.post("/ui/conta/senha")
def ui_conta_alterar_senha(
    request: Request,
    session: SessionDep,
    user: UIUser,
    senha_atual: Annotated[str, Form()],
    nova_senha: Annotated[str, Form()],
    confirmar_senha: Annotated[str, Form()],
) -> HTMLResponse:
    erro = None
    if not auth.verify_password(senha_atual, user.senha_hash):
        erro = "Senha atual invalida."
    elif not nova_senha:
        erro = "Nova senha obrigatoria."
    elif nova_senha != confirmar_senha:
        erro = "A confirmacao da senha nao confere."
    else:
        session.info["usuario_id"] = user.id
        usuario.change_password(session, user, nova_senha)

    return templates.TemplateResponse(
        request,
        "conta.html",
        {
            "user": user,
            "erro": erro,
            "sucesso": None if erro else "Senha alterada.",
        },
        status_code=400 if erro else 200,
    )
