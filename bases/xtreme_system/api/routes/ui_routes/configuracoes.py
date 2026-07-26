"""HTMX routes for configuracoes."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import structlog
from fastapi import BackgroundTasks, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_empresa_dir,
    _validar_uploads,
)
from xtreme_system.api.setup import app
from xtreme_system.database.core import register_post_commit, register_post_rollback
from xtreme_system.empresa import core as empresa
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
    config_empresa = empresa.get_config(session)
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": config,
            "config_empresa": config_empresa,
            "aba": "banco",
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
            evolution_api_key=evolution_api_key or atual.evolution_api_key,
            evolution_instance=evolution_instance,
            evolution_group_id=evolution_group_id,
            mensagem_template=mensagem_template,
        ),
        user.id,
    )
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": config,
            "config_empresa": empresa.get_config(session),
            "sucesso": "Configurações salvas.",
            "aba": "whatsapp",
        },
    )


@app.post("/ui/configuracoes/empresa")
def ui_configuracoes_empresa_salvar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    nome: Annotated[str, Form()] = "",
    endereco: Annotated[str, Form()] = "",
    bairro: Annotated[str, Form()] = "",
    cidade: Annotated[str, Form()] = "",
    uf: Annotated[str, Form()] = "",
    cep: Annotated[str, Form()] = "",
    telefone: Annotated[str, Form()] = "",
    cnpj: Annotated[str, Form()] = "",
    signatario: Annotated[str, Form()] = "",
) -> HTMLResponse:
    config_empresa = empresa.atualizar_config(
        session,
        empresa.EmpresaConfigUpdate(
            nome=nome,
            endereco=endereco,
            bairro=bairro,
            cidade=cidade,
            uf=uf,
            cep=cep,
            telefone=telefone,
            cnpj=cnpj,
            signatario=signatario,
        ),
    )
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": whatsapp.get_config(session),
            "config_empresa": config_empresa,
            "sucesso": "Dados da empresa salvos.",
            "aba": "empresa",
        },
    )


_EXTENSOES_LOGO = {".jpg", ".jpeg", ".png", ".webp"}


def _pagina_empresa(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    config_empresa: empresa.EmpresaConfig,
    *,
    erro: str | None = None,
    sucesso: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": whatsapp.get_config(session),
            "config_empresa": config_empresa,
            "erro": erro,
            "sucesso": sucesso,
            "aba": "empresa",
        },
    )


@app.post("/ui/configuracoes/empresa/logo")
def ui_configuracoes_empresa_logo_enviar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    logo: Annotated[UploadFile, File()],
) -> HTMLResponse:
    sufixo = Path(logo.filename or "").suffix.lower()
    if sufixo not in _EXTENSOES_LOGO:
        exts = ", ".join(sorted(_EXTENSOES_LOGO))
        return _pagina_empresa(
            request,
            session,
            user,
            empresa.get_config(session),
            erro=f"O logo deve ser uma imagem (aceitos: {exts})",
        )
    erro = _validar_uploads([logo])
    if erro:
        return _pagina_empresa(
            request, session, user, empresa.get_config(session), erro=erro
        )

    url_anterior = empresa.get_config(session).logo_url
    filename = f"{uuid4().hex}{sufixo}"
    upload_dir = _uploads_empresa_dir()
    path = upload_dir / filename
    tmp_path = upload_dir / f".{filename}.tmp"
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.write_bytes(logo.file.read())
        with tmp_path.open("rb") as tmp_file:
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    def _remover_novo_logo(*, path: Path = path, tmp_path: Path = tmp_path) -> None:
        path.unlink(missing_ok=True)
        tmp_path.unlink(missing_ok=True)

    register_post_rollback(session, _remover_novo_logo)
    try:
        config_empresa = empresa.definir_logo(
            session, f"/static/uploads/empresa/{filename}"
        )
    except Exception:
        _remover_novo_logo()
        raise

    anterior = _uploaded_file_path(url_anterior) if url_anterior else None
    if anterior is not None and anterior != path:

        def _remover_logo_anterior(*, anterior: Path = anterior) -> None:
            _remover_upload(anterior)

        register_post_commit(session, _remover_logo_anterior)
    return _pagina_empresa(
        request, session, user, config_empresa, sucesso="Logo atualizado."
    )


@app.post("/ui/configuracoes/empresa/logo/excluir")
def ui_configuracoes_empresa_logo_excluir(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    url_anterior = empresa.get_config(session).logo_url
    config_empresa = empresa.remover_logo(session)
    anterior = _uploaded_file_path(url_anterior) if url_anterior else None
    if anterior is not None:
        _remover_upload(anterior)
    return _pagina_empresa(
        request, session, user, config_empresa, sucesso="Logo removido."
    )


@app.post("/ui/configuracoes/exportar")
def ui_configuracoes_exportar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> Response:
    _fechar_transacao_da_rota(session, user)
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
    try:
        exportacao.dump_database_to_file(tmp_path)
    except exportacao.ExportacaoError as exc:
        os.unlink(tmp_path)
        config = whatsapp.get_config(session)
        return templates.TemplateResponse(
            request,
            "configuracoes.html",
            {
                "user": user,
                "config": config,
                "config_empresa": empresa.get_config(session),
                "erro": str(exc),
                "aba": "banco",
            },
            status_code=500,
        )
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"humpback_dump_{ts}.dump"
    background = BackgroundTasks()
    background.add_task(os.unlink, tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=background,
    )


@app.post("/ui/configuracoes/importar")
async def ui_configuracoes_importar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    arquivo: Annotated[UploadFile, File()],
) -> HTMLResponse:
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
        while chunk := await arquivo.read(1024 * 1024):
            f.write(chunk)
    _fechar_transacao_da_rota(session, user)
    try:
        await run_in_threadpool(exportacao.restore_database_from_file, tmp_path)
    except exportacao.ExportacaoError as exc:
        config = whatsapp.get_config(session)
        return templates.TemplateResponse(
            request,
            "configuracoes.html",
            {
                "user": user,
                "config": config,
                "config_empresa": empresa.get_config(session),
                "erro": str(exc),
                "aba": "banco",
            },
        )
    finally:
        os.unlink(tmp_path)
    session.expire_all()
    config = whatsapp.get_config(session)
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": config,
            "config_empresa": empresa.get_config(session),
            "sucesso": "Dados importados com sucesso.",
            "aba": "banco",
        },
    )
