"""Helpers de upload: persistir metadados no DB e gravar arquivos em pós-commit."""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.database.core import register_post_commit

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
    """Cria cada registro no DB e grava o arquivo em disco só após o commit.

    Se ``create_fn`` lança, nenhum arquivo é gravado em disco.
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
        if actor_id is None:
            create_fn(session, data)
        else:
            create_fn(session, data, actor_id)
        pending_paths = session.info.setdefault(_PENDING_UPLOAD_PATHS_KEY, set())
        pending_paths.add(str(path))

        def _write_file_after_commit(
            *,
            path: Path = path,
            content: bytes = content,
            upload_dir: Path = upload_dir,
            session: Session = session,
        ) -> None:
            try:
                upload_dir.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            finally:
                pending = session.info.get(_PENDING_UPLOAD_PATHS_KEY)
                if pending is not None:
                    pending.discard(str(path))
                    if not pending:
                        session.info.pop(_PENDING_UPLOAD_PATHS_KEY, None)

        register_post_commit(
            session,
            _write_file_after_commit,
        )


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
