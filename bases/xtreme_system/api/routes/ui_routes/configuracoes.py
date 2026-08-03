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
from xtreme_system.api.routes.ui_routes.upload_files import (
    remover_upload,
    uploaded_file_path,
)
from xtreme_system.api.routes.ui_routes.upload_paths import (
    uploads_empresa_dir,
)
from xtreme_system.api.routes.ui_routes.upload_validation import (
    validar_uploads,
)
from xtreme_system.api.setup import app
from xtreme_system.database.core import (
    DatabaseRestoreInProgressError,
    database_traffic_lock,
    detach_request_session,
    register_post_commit,
)
from xtreme_system.empresa import core as empresa
from xtreme_system.exportacao import core as exportacao
from xtreme_system.upload_file.core import escrever_upload_atomico
from xtreme_system.usuario import core as usuario
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)


@app.get("/ui/configuracoes")
def ui_configuracoes(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    config = whatsapp.get_config(session)
    return _pagina_empresa(
        request,
        session,
        user,
        empresa.get_config(session),
        config=config,
        aba="banco",
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
    return _pagina_empresa(
        request,
        session,
        user,
        empresa.get_config(session),
        config=config,
        sucesso="Configurações salvas.",
        aba="whatsapp",
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
    return _pagina_empresa(
        request,
        session,
        user,
        config_empresa,
        sucesso="Dados da empresa salvos.",
    )


_EXTENSOES_LOGO = {".jpg", ".jpeg", ".png", ".webp"}


def _pagina_empresa(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    config_empresa: empresa.EmpresaConfig,
    *,
    config: whatsapp.WhatsappConfig | None = None,
    erro: str | None = None,
    sucesso: str | None = None,
    aba: str = "empresa",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": config or whatsapp.get_config(session),
            "config_empresa": config_empresa,
            "erro": erro,
            "sucesso": sucesso,
            "aba": aba,
        },
        status_code=status_code,
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
    erro = validar_uploads([logo])
    if erro:
        return _pagina_empresa(
            request, session, user, empresa.get_config(session), erro=erro
        )

    url_anterior = empresa.get_config(session).logo_url
    filename = f"{uuid4().hex}{sufixo}"
    upload_dir = uploads_empresa_dir()
    path = escrever_upload_atomico(session, upload_dir, filename, logo.file.read())

    def _remover_novo_logo() -> None:
        path.unlink(missing_ok=True)
        (upload_dir / f".{filename}.tmp").unlink(missing_ok=True)

    try:
        config_empresa = empresa.definir_logo(
            session, f"/static/uploads/empresa/{filename}"
        )
    except Exception:
        _remover_novo_logo()
        raise

    anterior = uploaded_file_path(url_anterior) if url_anterior else None
    if anterior is not None and anterior != path:

        def _remover_logo_anterior(*, anterior: Path = anterior) -> None:
            remover_upload(anterior)

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
    anterior = uploaded_file_path(url_anterior) if url_anterior else None
    if anterior is not None:
        remover_upload(anterior)
    return _pagina_empresa(
        request, session, user, config_empresa, sucesso="Logo removido."
    )


@app.post("/ui/configuracoes/exportar")
def ui_configuracoes_exportar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> Response:
    detach_request_session(request, keep=(user,))
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
    try:
        exportacao.dump_database_to_file(tmp_path)
    except exportacao.ExportacaoError as exc:
        os.unlink(tmp_path)
        config = whatsapp.get_config(session)
        return _pagina_empresa(
            request,
            session,
            user,
            empresa.get_config(session),
            config=config,
            erro=str(exc),
            aba="banco",
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
    log_context = {
        "actor_id": user.id,
        "actor_username": user.username,
        "operation": "database_restore_import",
    }
    logger.info("database_restore_started", **log_context)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
            tmp_path = f.name
            while chunk := await arquivo.read(1024 * 1024):
                f.write(chunk)
        detach_request_session(request, keep=(user,))
        await run_in_threadpool(exportacao.restore_database_from_file, tmp_path)
        logger.info("database_restore_succeeded", **log_context)
    except exportacao.RestoreEmAndamentoError as exc:
        logger.warning(
            "database_restore_failed",
            **log_context,
            outcome="already_in_progress",
            error=str(exc),
        )
        return HTMLResponse(f"<p>{exc}</p>", status_code=409)
    except exportacao.ExportacaoError as exc:
        logger.warning(
            "database_restore_failed",
            **log_context,
            outcome="error",
            error=str(exc),
        )
        try:
            with database_traffic_lock():
                config = whatsapp.get_config(session)
                return _pagina_empresa(
                    request,
                    session,
                    user,
                    empresa.get_config(session),
                    config=config,
                    erro=str(exc),
                    aba="banco",
                )
        except DatabaseRestoreInProgressError:
            return HTMLResponse(
                "<p>O banco está sendo restaurado. Tente novamente em instantes.</p>",
                status_code=503,
            )
    except Exception:
        logger.exception(
            "database_restore_failed",
            **log_context,
            outcome="unexpected_error",
        )
        raise
    finally:
        if tmp_path is not None:
            os.unlink(tmp_path)
    try:
        with database_traffic_lock():
            session.expire_all()
            config = whatsapp.get_config(session)
            return _pagina_empresa(
                request,
                session,
                user,
                empresa.get_config(session),
                config=config,
                sucesso="Dados importados com sucesso.",
                aba="banco",
            )
    except DatabaseRestoreInProgressError:
        return HTMLResponse(
            "<p>O banco está sendo restaurado. Tente novamente em instantes.</p>",
            status_code=503,
        )
