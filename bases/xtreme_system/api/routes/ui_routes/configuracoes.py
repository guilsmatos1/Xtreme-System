"""HTMX routes for configuracoes."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, templates, validar_csrf
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
from xtreme_system.database.core import (
    DatabaseRestoreInProgressError,
    database_traffic_lock,
    detach_request_session,
    register_post_commit,
)
from xtreme_system.empresa import core as empresa
from xtreme_system.exportacao import core as exportacao
from xtreme_system.rsd import core as rsd
from xtreme_system.upload_file.core import escrever_upload_atomico
from xtreme_system.usuario import core as usuario
from xtreme_system.whatsapp import core as whatsapp

router = APIRouter()

logger = structlog.get_logger(__name__)


@router.get("/ui/configuracoes")
def ui_configuracoes(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    aba: Annotated[str, Query()] = "banco",
) -> HTMLResponse:
    mensagem = {
        "rsd-salvo": "Configurações RSD salvas.",
    }.get(request.cookies.get("ui_flash") or "")
    aba = aba if aba in {"banco", "whatsapp", "rsd", "tema", "empresa"} else "banco"
    response = _pagina_empresa(
        request,
        session,
        user,
        empresa.get_config(session),
        aba=aba,
        sucesso=mensagem,
    )
    if request.cookies.get("ui_flash"):
        response.delete_cookie("ui_flash", path="/")
    return response


@router.post("/ui/configuracoes")
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


@router.post("/ui/configuracoes/rsd")
def ui_configuracoes_rsd_salvar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    _csrf: Annotated[None, Depends(validar_csrf)],
    email: Annotated[str, Form()] = "",
    senha: Annotated[str, Form()] = "",
    base_url: Annotated[str, Form()] = "",
    rsd_teste_prova: Annotated[str, Form()] = "",
) -> Response:
    atual = rsd.get_config(session)
    try:
        rsd.atualizar_config(
            session,
            rsd.RsdConfigUpdate(
                email=email,
                # Campo vazio = manter a senha atual; `atualizar_config` já cobre
                # esse caso (só reencripta quando `senha` vem preenchida).
                senha=senha,
                base_url=base_url or atual.base_url,
                teste_prova=rsd_teste_prova,
            ),
            user.id,
        )
    except rsd.RsdError as exc:
        return _pagina_empresa(
            request,
            session,
            user,
            empresa.get_config(session),
            config_rsd=atual,
            erro=str(exc),
            aba="rsd",
            status_code=400,
        )
    response = RedirectResponse("/ui/configuracoes?aba=rsd", status_code=303)
    response.set_cookie(
        "ui_flash",
        "rsd-salvo",
        max_age=60,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/ui/configuracoes/rsd/teste")
def ui_configuracoes_rsd_teste(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    _csrf: Annotated[None, Depends(validar_csrf)],
    email: Annotated[str, Form()] = "",
    senha: Annotated[str, Form()] = "",
    base_url: Annotated[str, Form()] = "",
) -> HTMLResponse:
    """Testa com os valores do formulário (ainda não salvos), não com o que
    já está persistido — ver docs/analise-erros-rsd.md sobre o botão testar
    conexão silenciosamente ignorar e-mail/senha recém-digitados."""
    config_rsd = rsd.get_config(session)
    config_wa = whatsapp.get_config(session)
    config_empresa = empresa.get_config(session)
    config_rsd_form = rsd.RsdConfig(
        id=config_rsd.id,
        email=email.strip(),
        base_url=base_url.strip() or config_rsd.base_url,
        # O rascunho nunca carrega nem renderiza a senha digitada.
        senha="",
        revogada=False,
    )
    try:
        client = rsd.client_from_values(
            email=email, senha=senha, base_url=base_url, config=config_rsd
        )
    except rsd.RsdError as exc:
        if request.headers.get("HX-Request"):
            return _rsd_teste_resultado(
                request,
                sucesso=False,
                erro=rsd.mensagem_teste(exc),
                teste_prova="",
            )
        return _pagina_empresa(
            request,
            session,
            user,
            config_empresa,
            config=config_wa,
            config_rsd=config_rsd_form,
            erro=str(exc),
            aba="rsd",
            status_code=400,
            rsd_testado=True,
            rsd_teste_erro=rsd.mensagem_teste(exc),
        )
    # `perfil` é relationship, não coluna — detach_request_session só
    # pré-carrega colunas (`state.mapper.column_attrs`). O template
    # renderizado abaixo (nav de base.html) acessa `user.perfil` via
    # `pode_acessar`; sem isto, gera DetachedInstanceError depois que a
    # sessão já foi fechada.
    _ = user.perfil
    detach_request_session(request, keep=(user, config_rsd, config_wa, config_empresa))
    try:
        client.open()
        client.testar_conexao()
    except rsd.RsdError as exc:
        logger.warning("rsd_teste_conexao_falhou", **rsd.contexto_log(exc))
        rsd.registrar_teste_config_persistente(
            email=email,
            senha=senha or rsd.senha_config(config_rsd),
            base_url=base_url or config_rsd.base_url,
            sucesso=False,
            erro=exc,
        )
        resultado = _rsd_teste_resultado(
            request,
            sucesso=False,
            erro=rsd.mensagem_teste(exc),
            teste_prova="",
        )
        if request.headers.get("HX-Request"):
            return resultado
        return _pagina_empresa(
            request,
            session,
            user,
            config_empresa,
            config=config_wa,
            config_rsd=config_rsd_form,
            erro=str(exc),
            aba="rsd",
            status_code=400,
            rsd_testado=True,
            rsd_teste_erro=rsd.mensagem_teste(exc),
        )
    finally:
        client.close()
    rsd.registrar_teste_config_persistente(
        email=email,
        senha=senha or rsd.senha_config(config_rsd),
        base_url=base_url or config_rsd.base_url,
        sucesso=True,
    )
    teste_prova = rsd.emitir_teste_prova(
        email=email,
        senha=senha or rsd.senha_config(config_rsd),
        base_url=base_url or config_rsd.base_url,
    )
    if request.headers.get("HX-Request"):
        return _rsd_teste_resultado(
            request,
            sucesso=True,
            erro=None,
            teste_prova=teste_prova,
        )
    return _pagina_empresa(
        request,
        session,
        user,
        config_empresa,
        config=config_wa,
        config_rsd=config_rsd_form,
        sucesso="Conexão com o portal RSD OK. Salve para ativar a configuração.",
        aba="rsd",
        rsd_testado=True,
        rsd_teste_prova=teste_prova,
    )


@router.post("/ui/configuracoes/rsd/revogar")
def ui_configuracoes_rsd_revogar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    _csrf: Annotated[None, Depends(validar_csrf)],
) -> HTMLResponse:
    config_rsd = rsd.revogar_config(session, user.id)
    return _pagina_empresa(
        request,
        session,
        user,
        empresa.get_config(session),
        config_rsd=config_rsd,
        sucesso="Credencial RSD revogada e removida.",
        aba="rsd",
    )


@router.post("/ui/configuracoes/empresa")
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
    config_rsd: rsd.RsdConfig | None = None,
    erro: str | None = None,
    sucesso: str | None = None,
    aba: str = "empresa",
    status_code: int = 200,
    limpar_senha_rsd: bool = False,
    rsd_testado: bool = False,
    rsd_teste_erro: str | None = None,
    rsd_teste_prova: str = "",
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request,
        "configuracoes.html",
        {
            "user": user,
            "config": config or whatsapp.get_config(session),
            "config_rsd": config_rsd or rsd.get_config(session),
            "config_empresa": config_empresa,
            "erro": erro,
            "sucesso": sucesso,
            "aba": aba,
            "rsd_senha_salva": limpar_senha_rsd,
            "rsd_testado": rsd_testado,
            "rsd_teste_erro": rsd_teste_erro,
            "rsd_teste_prova": rsd_teste_prova,
            "rsd_ok": rsd.configurado(config_rsd or rsd.get_config(session)),
            "rsd_status": rsd.status_config(
                config_rsd or rsd.get_config(session)
            ).value,
        },
        status_code=status_code,
    )
    # Sem isto, o botão "Voltar" do navegador pode restaurar do bfcache o
    # snapshot da página anterior ao último save (credenciais/dados velhos),
    # em vez de refazer o GET — ver docs/agents ou o achado do bug de RSD
    # "email salvo não aparece ao voltar".
    response.headers["Cache-Control"] = "no-store"
    return response


def _rsd_teste_resultado(
    request: Request,
    *,
    sucesso: bool,
    erro: str | None,
    teste_prova: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_rsd_test_result.html",
        {
            "sucesso": sucesso,
            "erro": erro,
            "teste_prova": teste_prova,
        },
        status_code=200 if sucesso else 400,
    )


@router.post("/ui/configuracoes/empresa/logo")
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


@router.post("/ui/configuracoes/empresa/logo/excluir")
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


@router.post("/ui/configuracoes/exportar")
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


@router.post("/ui/configuracoes/importar")
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
