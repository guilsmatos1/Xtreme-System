"""Helpers de upload: gravar arquivos e persistir metadados no DB."""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.database.core import register_post_rollback

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
    for arquivo in arquivos:
        if not arquivo.filename:
            continue
        suffix = Path(arquivo.filename).suffix.lower()
        filename = f"{uuid4().hex}{suffix}"
        path = upload_dir / filename
        content = arquivo.file.read()
        data = schema.model_validate(
            {fk_field: fk_id, "url": f"{url_prefix}/{filename}"}
        )
        upload_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

        def _remove_file_on_rollback(*, path: Path = path) -> None:
            path.unlink(missing_ok=True)

        register_post_rollback(session, _remove_file_on_rollback)
        try:
            if actor_id is None:
                create_fn(session, data)
            else:
                create_fn(session, data, actor_id)
        except Exception:
            _remove_file_on_rollback()
            raise


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
