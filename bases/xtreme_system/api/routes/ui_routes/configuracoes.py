"""HTMX routes for configuracoes."""

from typing import Annotated

import structlog
from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.setup import app
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)

# ---- Configurações (admin-only) ----


@app.get("/ui/configuracoes")
def ui_configuracoes(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    config = whatsapp.get_config(session)
    return templates.TemplateResponse(
        request, "configuracoes.html", {"user": user, "config": config}
    )


@app.post("/ui/configuracoes")
def ui_configuracoes_salvar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    evolution_api_url: Annotated[str, Form()] = "",
    evolution_api_key: Annotated[str, Form()] = "",
    evolution_instance: Annotated[str, Form()] = "",
    evolution_group_id: Annotated[str, Form()] = "",
    mensagem_template: Annotated[str, Form()] = "",
) -> HTMLResponse:
    atual = whatsapp.get_config(session)
    config = whatsapp.atualizar_config(
        session,
        whatsapp.WhatsappConfigUpdate(
            evolution_api_url=evolution_api_url,
            # Campo vazio no formulário significa "manter a chave atual";
            # assim a secret não precisa ser reenviada nem renderizada no HTML.
            evolution_api_key=evolution_api_key or atual.evolution_api_key,
            evolution_instance=evolution_instance,
            evolution_group_id=evolution_group_id,
            mensagem_template=mensagem_template,
        ),
    )
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {"user": user, "config": config, "sucesso": "Configurações salvas."},
    )
