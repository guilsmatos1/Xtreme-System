"""Unit tests for uploads helpers (salvar_arquivos, remover_orfaos)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.api.routes.ui_routes.uploads import (
    remover_orfaos,
    salvar_arquivos,
)


class _FakeFile:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, _n: int = -1) -> bytes:
        return self._data

    def seek(self, offset: int, whence: int = 0) -> int:
        return len(self._data) + offset if whence == 2 else offset

    def tell(self) -> int:
        return len(self._data)


class _FakeUpload:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self.content_type = ""
        self._size = len(data)
        self.file = _FakeFile(data)

    @property
    def size(self) -> int:
        return self._size


class _FakeDoc:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakeSchema(BaseModel):
    veiculo_id: int
    url: str


def test_salvar_arquivos_happy_path(tmp_path: Path) -> None:
    calls: list[Any] = []

    def create_fn(_session: Session, data: Any) -> Any:
        calls.append(data)

    salvar_arquivos(
        cast(Session, object()),
        upload_dir=tmp_path,
        url_prefix="/static/uploads/veiculos/1",
        create_fn=create_fn,
        schema=_FakeSchema,
        fk_field="veiculo_id",
        fk_id=1,
        arquivos=[
            _FakeUpload("foto.jpg", b"dados-foto"),  # type: ignore[list-item]
            _FakeUpload("doc.pdf", b"dados-doc"),  # type: ignore[list-item]
        ],
    )

    assert len(calls) == 2
    assert calls[0].veiculo_id == 1
    assert calls[0].url.startswith("/static/uploads/veiculos/1/")
    assert calls[0].url.endswith(".jpg")
    assert calls[1].url.endswith(".pdf")

    files_on_disk = sorted(tmp_path.iterdir(), key=lambda p: p.suffix)
    assert len(files_on_disk) == 2
    assert files_on_disk[0].read_bytes() == b"dados-foto"
    assert files_on_disk[1].read_bytes() == b"dados-doc"


def test_salvar_arquivos_ignora_arquivo_sem_filename(tmp_path: Path) -> None:
    calls: list[Any] = []

    def create_fn(_session: Session, data: Any) -> Any:
        calls.append(data)

    salvar_arquivos(
        cast(Session, object()),
        upload_dir=tmp_path,
        url_prefix="/static/uploads/veiculos/1",
        create_fn=create_fn,
        schema=_FakeSchema,
        fk_field="veiculo_id",
        fk_id=1,
        arquivos=[_FakeUpload("", b"")],  # type: ignore[list-item]
    )

    assert calls == []
    assert not list(tmp_path.iterdir())


def test_salvar_arquivos_falha_create_remove_arquivo(tmp_path: Path) -> None:
    def falha_create(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db indisponivel")

    with pytest.raises(RuntimeError, match="db indisponivel"):
        salvar_arquivos(
            cast(Session, object()),
            upload_dir=tmp_path,
            url_prefix="/static/uploads/veiculos/1",
            create_fn=cast(Callable[[Session, Any], Any], falha_create),
            schema=_FakeSchema,
            fk_field="veiculo_id",
            fk_id=1,
            arquivos=[_FakeUpload("foto.jpg", b"dados")],  # type: ignore[list-item]
        )

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_remover_orfaos_deleta_db_se_arquivo_inexistente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted: list[Any] = []

    def delete_fn(_session: Session, doc: Any) -> None:
        deleted.append(doc)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.uploads._uploaded_file_path",
        lambda _url: Path("/nonexistent/file.jpg"),
    )

    remover_orfaos(
        cast(Session, object()),
        [_FakeDoc("/static/uploads/veiculos/1/foto.jpg")],
        cast(Callable[[Session, Any], None], delete_fn),
    )

    assert len(deleted) == 1


def test_remover_orfaos_mantem_se_arquivo_existe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    deleted: list[Any] = []

    def delete_fn(_session: Session, doc: Any) -> None:
        deleted.append(doc)

    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"dados")

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.uploads._uploaded_file_path",
        lambda _url: arquivo,
    )

    remover_orfaos(
        cast(Session, object()),
        [_FakeDoc("/static/uploads/veiculos/1/foto.jpg")],
        cast(Callable[[Session, Any], None], delete_fn),
    )

    assert deleted == []
