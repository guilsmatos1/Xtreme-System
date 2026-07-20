"""HTMX routes for configuracoes."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.setup import app
from xtreme_system.exportacao import core as exportacao
from xtreme_system.usuario import core as usuario
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)


def _fechar_transacao_da_rota(session: Session, user: usuario.Usuario) -> None:
    _ = user.id, user.username, user.papel, user.perfil_id
    session.expunge(user)
    session.rollback()
    session.close()


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


@app.post("/ui/configuracoes/exportar")
def ui_configuracoes_exportar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> Response:
    _fechar_transacao_da_rota(session, user)
    try:
        dump = exportacao.dump_database()
    except exportacao.ExportacaoError as exc:
        config = whatsapp.get_config(session)
        return templates.TemplateResponse(
            request,
            "configuracoes.html",
            {"user": user, "config": config, "erro": str(exc)},
            status_code=500,
        )
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"humpback_dump_{ts}.dump"
    return Response(
        content=dump,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/ui/configuracoes/importar")
def ui_configuracoes_importar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    arquivo: Annotated[UploadFile, File()],
) -> HTMLResponse:
    conteudo = arquivo.file.read()
    _fechar_transacao_da_rota(session, user)
    try:
        exportacao.restore_database(conteudo)
    except exportacao.ExportacaoError as exc:
        config = whatsapp.get_config(session)
        return templates.TemplateResponse(
            request,
            "configuracoes.html",
            {"user": user, "config": config, "erro": str(exc)},
        )
    session.expire_all()
    config = whatsapp.get_config(session)
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {"user": user, "config": config, "sucesso": "Dados importados com sucesso."},
    )
