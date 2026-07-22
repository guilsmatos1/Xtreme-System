"""HTMX routes for configuracoes."""

from pathlib import Path
from typing import Annotated

import structlog
from fastapi import File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_empresa_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    pending_upload_paths,
    salvar_arquivos,
)
from xtreme_system.api.setup import app
from xtreme_system.empresa import core as empresa
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)

_EXTENSOES_LOGO = {".jpg", ".jpeg", ".png", ".webp"}

# ---- Configurações (admin-only) ----


@app.get("/ui/configuracoes")
def ui_configuracoes(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    config = whatsapp.get_config(session)
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": config,
            "empresa": empresa.get_config(session),
            "pending_upload_paths": pending_upload_paths(session),
        },
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
        {
            "user": user,
            "config": config,
            "empresa": empresa.get_config(session),
            "pending_upload_paths": pending_upload_paths(session),
            "sucesso": "Configurações salvas.",
        },
    )


# ---- Logo da empresa ----


def _logo_partial(
    request: Request,
    session: Session,
    *,
    erro: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_empresa_logo.html",
        {
            "empresa": empresa.get_config(session),
            "pending_upload_paths": pending_upload_paths(session),
            "erro": erro,
        },
        status_code=status_code,
    )


@app.post("/ui/configuracoes/empresa/logo")
def ui_empresa_logo_upload(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    logo: Annotated[UploadFile, File()],
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    extensao = Path(logo.filename or "").suffix.lower()
    if extensao not in _EXTENSOES_LOGO:
        exts = ", ".join(sorted(_EXTENSOES_LOGO))
        return _logo_partial(
            request,
            session,
            erro=f"Tipo não permitido para logo (aceitos: {exts})",
            status_code=400,
        )
    erro = _validar_uploads([logo])
    if erro:
        return _logo_partial(request, session, erro=erro, status_code=400)
    anterior = empresa.get_config(session).logo_url
    salvar_arquivos(
        session,
        upload_dir=_uploads_empresa_dir(),
        url_prefix="/static/uploads/empresa",
        create_fn=empresa.definir_logo,
        schema=empresa.EmpresaLogoCreate,
        fk_field="id",
        fk_id=1,
        arquivos=[logo],
        actor_id=user.id,
    )
    _remover_logo_do_disco(anterior)
    return _logo_partial(request, session)


@app.post("/ui/configuracoes/empresa/logo/excluir")
def ui_empresa_logo_excluir(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    anterior = empresa.get_config(session).logo_url
    empresa.remover_logo(session)
    _remover_logo_do_disco(anterior)
    return _logo_partial(request, session)


def _remover_logo_do_disco(url: str) -> None:
    if not url:
        return
    path = _uploaded_file_path(url)
    if path is not None:
        _remover_upload(path)
