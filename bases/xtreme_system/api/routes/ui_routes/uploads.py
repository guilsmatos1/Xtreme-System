"""Helpers de upload: gravar arquivos e persistir metadados no DB."""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.api.routes.ui_routes.upload_files import (
    remover_upload,
    uploaded_file_path,
)
from xtreme_system.api.routes.ui_routes.upload_validation import validar_uploads
from xtreme_system.upload_file.core import escrever_upload_atomico

_PENDING_UPLOAD_PATHS_KEY = "_pending_upload_paths"


def pending_upload_paths(session: Session) -> set[str]:
    info = getattr(session, "info", None)
    if info is None:
        return set()
    return set(info.get(_PENDING_UPLOAD_PATHS_KEY, set()))


def salvar_arquivos(
    session: Session,
    *,
    upload_dir: Path,
    url_prefix: str,
    create_fn: Callable[..., Any],
    schema: type[BaseModel],
    fk_field: str,
    fk_id: int,
    arquivos: list[UploadFile],
    actor_id: int | None = None,
) -> None:
    """Grava cada arquivo em disco e cria o registro correspondente no DB.

    Se ``create_fn`` lança ou a transação sofre rollback, arquivos gravados
    nesta chamada são removidos.
    Arquivos sem ``filename`` são ignorados.
    """
    cleanup_paths: list[tuple[Path, Path]] = []
    try:
        for arquivo in arquivos:
            if not arquivo.filename:
                continue
            suffix = Path(arquivo.filename).suffix.lower()
            filename = f"{uuid4().hex}{suffix}"
            content = arquivo.file.read()
            data = schema.model_validate(
                {fk_field: fk_id, "url": f"{url_prefix}/{filename}"}
            )
            path = escrever_upload_atomico(session, upload_dir, filename, content)
            cleanup_paths.append((path, upload_dir / f".{filename}.tmp"))
            if actor_id is None:
                create_fn(session, data)
            else:
                create_fn(session, data, actor_id)
    except Exception:
        for path, tmp_path in cleanup_paths:
            path.unlink(missing_ok=True)
            tmp_path.unlink(missing_ok=True)
        raise


def salvar_anexos_entidade(
    session: Session,
    *,
    upload_dir: Path,
    url_prefix: str,
    create_fn: Callable[..., Any],
    schema: type[BaseModel],
    fk_field: str,
    fk_id: int,
    arquivos: list[UploadFile],
    actor_id: int,
) -> str | None:
    erro = validar_uploads(arquivos)
    if erro:
        return erro
    session.info["usuario_id"] = actor_id
    salvar_arquivos(
        session,
        upload_dir=upload_dir,
        url_prefix=url_prefix,
        create_fn=create_fn,
        schema=schema,
        fk_field=fk_field,
        fk_id=fk_id,
        arquivos=arquivos,
        actor_id=actor_id,
    )
    return None


def excluir_anexo_entidade(
    session: Session,
    *,
    anexo: Any,
    parent_field: str,
    parent_id: int,
    delete_fn: Callable[..., Any],
    actor_id: int,
    not_found_detail: str,
) -> None:
    if getattr(anexo, parent_field) != parent_id:
        raise HTTPException(status_code=404, detail=not_found_detail)
    session.info["usuario_id"] = actor_id
    delete_fn(session, anexo, actor_id)
    path = uploaded_file_path(anexo.url or "")
    if path is not None:
        remover_upload(path)


def remover_orfaos(
    _session: Session,
    _docs: Iterable[Any],
    _delete_fn: Callable[[Session, Any], None],
) -> None:
    """Mantido por compatibilidade; não remove registros no fluxo de leitura.

    A reconciliação de órfãos deve ocorrer em um processo explícito de limpeza,
    não durante a abertura de modais ou outras leituras.
    """
    return
