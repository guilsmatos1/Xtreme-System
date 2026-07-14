"""Helpers de upload: salvar arquivos em disco + DB e remover registros órfãos."""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
)


def salvar_arquivos(
    session: Session,
    *,
    upload_dir: Path,
    url_prefix: str,
    create_fn: Callable[[Session, Any], Any],
    schema: type[BaseModel],
    fk_field: str,
    fk_id: int,
    arquivos: list[UploadFile],
) -> None:
    """Persiste cada arquivo em disco e cria o registro no DB.

    Se ``create_fn`` lança, o arquivo já gravado é removido do disco.
    Arquivos sem ``filename`` são ignorados.
    """
    for arquivo in arquivos:
        if not arquivo.filename:
            continue
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(arquivo.filename).suffix.lower()
        filename = f"{uuid4().hex}{suffix}"
        path = upload_dir / filename
        with path.open("wb") as f:
            f.write(arquivo.file.read())
        try:
            create_fn(
                session,
                schema.model_validate(
                    {fk_field: fk_id, "url": f"{url_prefix}/{filename}"}
                ),
            )
        except Exception:
            _remover_upload(path)
            raise


def remover_orfaos(
    session: Session,
    docs: Iterable[Any],
    delete_fn: Callable[[Session, Any], None],
) -> None:
    """Remove do DB registros cujo arquivo em disco não existe mais."""
    for doc in list(docs):
        path = _uploaded_file_path(doc.url or "")
        if path is not None and not path.exists():
            delete_fn(session, doc)
