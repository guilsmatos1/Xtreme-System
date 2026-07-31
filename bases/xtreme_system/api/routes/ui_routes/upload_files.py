"""Operations on persisted UI upload files."""

import contextlib
from collections.abc import Iterable
from pathlib import Path

from xtreme_system.api.routes.ui_routes import upload_paths
from xtreme_system.upload_file.core import (
    arquivo_disponivel as core_arquivo_disponivel,
)
from xtreme_system.upload_file.core import (
    uploaded_file_path as core_uploaded_file_path,
)

__all__ = ["arquivo_disponivel", "remover_upload", "uploaded_file_path"]


def uploaded_file_path(url: str) -> Path | None:
    return core_uploaded_file_path(url, ui_dir=upload_paths.ui_dir)


def arquivo_disponivel(url: str, pending_paths: Iterable[str] | None = None) -> bool:
    return core_arquivo_disponivel(url, pending_paths, ui_dir=upload_paths.ui_dir)


def remover_upload(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
