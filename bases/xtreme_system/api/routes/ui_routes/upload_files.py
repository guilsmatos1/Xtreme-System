"""Operations on persisted UI upload files."""

import contextlib
from collections.abc import Iterable
from pathlib import Path

from xtreme_system.api.routes.ui_routes import upload_paths
from xtreme_system.upload_file.core import uploaded_file_path


def _uploaded_file_path(url: str) -> Path | None:
    return uploaded_file_path(url, ui_dir=upload_paths.ui_dir)


def arquivo_disponivel(url: str, pending_paths: Iterable[str] | None = None) -> bool:
    path = _uploaded_file_path(url)
    if path is None:
        return False
    if pending_paths is not None and str(path) in set(pending_paths):
        return True
    return path.exists()


def _remover_upload(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
