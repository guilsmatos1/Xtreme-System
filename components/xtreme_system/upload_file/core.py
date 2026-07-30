"""Helpers for upload files stored under /static/uploads."""

from contextlib import suppress
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import object_session

from xtreme_system.database.core import register_post_commit

_SOURCE_UI_DIR = Path(__file__).resolve().parents[3] / "bases" / "xtreme_system" / "api"
_PACKAGE_UI_DIR = Path(__file__).resolve().parents[1] / "api"
_DEFAULT_UI_DIR = _SOURCE_UI_DIR if _SOURCE_UI_DIR.exists() else _PACKAGE_UI_DIR


def uploaded_file_path(url: str, *, ui_dir: Path | None = None) -> Path | None:
    if not url.startswith("/static/uploads/"):
        return None
    root = ui_dir or _DEFAULT_UI_DIR
    candidate = (root / url.lstrip("/")).resolve()
    uploads_root = (root / "static" / "uploads").resolve()
    if not candidate.is_relative_to(uploads_root):
        return None
    return candidate


def schedule_uploaded_file_delete(target: Any) -> None:
    path = uploaded_file_path(str(getattr(target, "url", "")))
    session = object_session(target)
    if path is None or session is None:
        return

    def _remove_file(*, path: Path = path) -> None:
        with suppress(FileNotFoundError):
            path.unlink()

    register_post_commit(session, _remove_file)


def register_upload_file_delete(model_cls: type[object]) -> None:
    def delete_upload_file(
        _mapper: object, _connection: object, target: object
    ) -> None:
        schedule_uploaded_file_delete(target)

    event.listen(model_cls, "after_delete", delete_upload_file)
