"""Unit tests for uploads helpers (salvar_arquivos, remover_orfaos)."""

import io
import os
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.api.routes.ui_routes.upload_files import (
    arquivo_disponivel,
    uploaded_file_path,
)
from xtreme_system.api.routes.ui_routes.upload_validation import (
    validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    remover_orfaos,
    salvar_arquivos,
)
from xtreme_system.cliente.core import Cliente, TipoCliente
from xtreme_system.compra.core import Compra
from xtreme_system.database.core import invoke_post_commit
from xtreme_system.imagem_comprovante_compra.core import ImagemComprovanteCompra
from xtreme_system.investidor.core import Investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo.core import TipoEntrada, TipoVeiculo, Veiculo


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


class _FakeSession:
    def __init__(self) -> None:
        self.info: dict[str, Any] = {}


class _FakeSchema(BaseModel):
    veiculo_id: int
    url: str


def test_salvar_arquivos_happy_path(tmp_path: Path) -> None:
    calls: list[Any] = []
    session = _FakeSession()

    def create_fn(_session: Session, data: Any) -> Any:
        calls.append(data)

    salvar_arquivos(
        cast(Session, session),
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
    session = _FakeSession()

    def create_fn(_session: Session, data: Any) -> Any:
        calls.append(data)

    salvar_arquivos(
        cast(Session, session),
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


def test_salvar_arquivos_falha_write_nao_cria_registro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []

    def create_fn(_session: Session, data: Any) -> Any:
        calls.append(data)

    def falha_write_bytes(_path: Path, _data: bytes) -> int:
        raise OSError("disco cheio")

    monkeypatch.setattr(Path, "write_bytes", falha_write_bytes)

    with pytest.raises(OSError, match="disco cheio"):
        salvar_arquivos(
            cast(Session, _FakeSession()),
            upload_dir=tmp_path,
            url_prefix="/static/uploads/veiculos/1",
            create_fn=create_fn,
            schema=_FakeSchema,
            fk_field="veiculo_id",
            fk_id=1,
            arquivos=[_FakeUpload("foto.jpg", b"dados")],  # type: ignore[list-item]
        )

    assert calls == []


def test_salvar_arquivos_falha_create_remove_arquivo(tmp_path: Path) -> None:
    def falha_create(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db indisponivel")

    with pytest.raises(RuntimeError, match="db indisponivel"):
        salvar_arquivos(
            cast(Session, _FakeSession()),
            upload_dir=tmp_path,
            url_prefix="/static/uploads/veiculos/1",
            create_fn=cast(Callable[[Session, Any], Any], falha_create),
            schema=_FakeSchema,
            fk_field="veiculo_id",
            fk_id=1,
            arquivos=[_FakeUpload("foto.jpg", b"dados")],  # type: ignore[list-item]
        )

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_salvar_arquivos_falha_no_lote_remove_arquivos_anteriores(
    tmp_path: Path,
) -> None:
    calls = 0

    def create_fn(_session: Session, _data: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("db indisponivel")

    with pytest.raises(RuntimeError, match="db indisponivel"):
        salvar_arquivos(
            cast(Session, _FakeSession()),
            upload_dir=tmp_path,
            url_prefix="/static/uploads/veiculos/1",
            create_fn=create_fn,
            schema=_FakeSchema,
            fk_field="veiculo_id",
            fk_id=1,
            arquivos=[
                _FakeUpload("foto.jpg", b"dados"),  # type: ignore[list-item]
                _FakeUpload("doc.pdf", b"pdf"),  # type: ignore[list-item]
            ],
        )

    assert calls == 2
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_salvar_arquivos_rollback_remove_arquivo(tmp_path: Path) -> None:
    session = _FakeSession()

    def create_fn(_session: Session, _data: Any) -> None:
        return

    salvar_arquivos(
        cast(Session, session),
        upload_dir=tmp_path,
        url_prefix="/static/uploads/veiculos/1",
        create_fn=create_fn,
        schema=_FakeSchema,
        fk_field="veiculo_id",
        fk_id=1,
        arquivos=[_FakeUpload("foto.jpg", b"dados")],  # type: ignore[list-item]
    )

    files_on_disk = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files_on_disk) == 1

    callbacks = session.info["_post_rollback_callbacks"]
    for callback in callbacks:
        callback()

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_remover_orfaos_nao_deleta_db_se_arquivo_inexistente() -> None:
    deleted: list[Any] = []

    def delete_fn(_session: Session, doc: Any) -> None:
        deleted.append(doc)

    remover_orfaos(
        cast(Session, object()),
        [_FakeDoc("/static/uploads/veiculos/1/foto.jpg")],
        cast(Callable[[Session, Any], None], delete_fn),
    )

    assert deleted == []


def test_remover_orfaos_mantem_se_arquivo_existe(
    tmp_path: Path,
) -> None:
    deleted: list[Any] = []

    def delete_fn(_session: Session, doc: Any) -> None:
        deleted.append(doc)

    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"dados")

    remover_orfaos(
        cast(Session, object()),
        [_FakeDoc("/static/uploads/veiculos/1/foto.jpg")],
        cast(Callable[[Session, Any], None], delete_fn),
    )

    assert deleted == []


def test_delete_parent_removes_upload_file_after_post_commit(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_ui = tmp_path / "ui"
    upload_dir = fake_ui / "static" / "uploads" / "compras" / "1" / "comprovantes"
    upload_dir.mkdir(parents=True)
    arquivo = upload_dir / "comprovante.pdf"
    arquivo.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr("xtreme_system.upload_file.core._DEFAULT_UI_DIR", fake_ui)

    compra = _compra_com_comprovante(
        "/static/uploads/compras/1/comprovantes/comprovante.pdf"
    )
    db_session.add(compra)
    db_session.flush()

    db_session.delete(compra)
    db_session.flush()
    assert arquivo.exists()

    invoke_post_commit(db_session)

    assert not arquivo.exists()


def test_delete_parent_keeps_upload_file_on_rollback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_ui = tmp_path / "ui"
    upload_dir = fake_ui / "static" / "uploads" / "compras" / "1" / "comprovantes"
    upload_dir.mkdir(parents=True)
    arquivo = upload_dir / "comprovante.pdf"
    arquivo.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr("xtreme_system.upload_file.core._DEFAULT_UI_DIR", fake_ui)

    compra = _compra_com_comprovante(
        "/static/uploads/compras/1/comprovantes/comprovante.pdf"
    )
    db_session.add(compra)
    db_session.flush()

    db_session.delete(compra)
    db_session.flush()
    db_session.rollback()

    assert arquivo.exists()


def _compra_com_comprovante(url: str) -> Compra:
    investidor = Investidor(nome="Investidor Upload")
    cliente = Cliente(
        nome="Cliente Upload",
        documento="00000000000",
        tipo=TipoCliente.pessoa_fisica,
    )
    veiculo = Veiculo(
        tipo=TipoVeiculo.carro,
        modelo="Modelo Upload",
        marca="Marca",
        cor="Preto",
        ano=2020,
        placa="UPL0001",
        chassi=None,
        renavam=None,
        km=None,
        preco=Decimal("10000.00"),
        procuracao=None,
        proprietario_registrado=None,
        tipo_entrada=TipoEntrada.compra,
        investidor=investidor,
    )
    compra = Compra(
        cliente=cliente,
        veiculo=veiculo,
        data_compra=date(2024, 1, 1),
        valor_compra=Decimal("10000.00"),
        debitos=None,
        observacoes=None,
    )
    compra.comprovantes.append(ImagemComprovanteCompra(url=url))
    return compra


def test_arquivo_disponivel_retorna_false_quando_arquivo_falta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.upload_paths.ui_dir", tmp_path
    )
    assert not arquivo_disponivel("/static/uploads/veiculos/1/foto.jpg")


def test_arquivo_disponivel_pendente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.upload_paths.ui_dir", tmp_path
    )
    path = tmp_path / "static" / "uploads" / "veiculos" / "1" / "foto.jpg"
    assert arquivo_disponivel("/static/uploads/veiculos/1/foto.jpg", {str(path)})


class _MagicFakeFile:
    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buf.seek(offset, whence)

    def tell(self) -> int:
        return self._buf.tell()


class _MagicFakeUpload:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self.content_type = ""
        self._size = len(data)
        self.file = _MagicFakeFile(data)

    @property
    def size(self) -> int:
        return self._size


class _MagicFakeUploadFull(_MagicFakeUpload):
    def __init__(self, filename: str, data: bytes, content_type: str) -> None:
        super().__init__(filename, data)
        self.content_type = content_type


def test_validar_uploads_aceita_jpeg_valido() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("foto.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF")]  # type: ignore[list-item]
    )
    assert result is None


def test_validar_uploads_aceita_png_valido() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("captura.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")]  # type: ignore[list-item]
    )
    assert result is None


def test_validar_uploads_aceita_pdf_valido() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("doc.pdf", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3")]  # type: ignore[list-item]
    )
    assert result is None


def test_validar_uploads_aceita_webp_valido() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("img.webp", b"RIFF\x00\x00\x00\x00WEBPVP8")]  # type: ignore[list-item]
    )
    assert result is None


def test_validar_uploads_rejeita_executavel_renomeado_jpg() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("foto.jpg", b"MZ\x90\x00\x03\x00\x00\x00")]  # type: ignore[list-item]
    )
    assert result is not None
    assert "Assinatura" in result


def test_validar_uploads_rejeita_txt_renomeado_png() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("img.png", b"not a png file at all")]  # type: ignore[list-item]
    )
    assert result is not None
    assert "Assinatura" in result


def test_validar_uploads_rejeita_exe_renomeado_pdf() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("relatorio.pdf", b"MZ\x90\x00")]  # type: ignore[list-item]
    )
    assert result is not None
    assert "Assinatura" in result


def test_validar_uploads_ignora_arquivo_sem_filename() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("", b"qualquer")]  # type: ignore[list-item]
    )
    assert result is None


def test_validar_uploads_mantem_seek_apos_verificacao() -> None:
    arq = _MagicFakeUpload("foto.jpg", b"\xff\xd8\xffABC")
    validar_uploads([arq])  # type: ignore[list-item]
    assert arq.file.tell() == 0


def test_validar_uploads_rejeita_arquivo_muito_curto() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("foto.jpg", b"\xff")]  # type: ignore[list-item]
    )
    assert result is not None


def test_validar_uploads_rejeita_conteudo_vazio() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("foto.jpg", b"")]  # type: ignore[list-item]
    )
    assert result is not None


def test_validar_uploads_ainda_rejeita_extensao_nao_permitida() -> None:
    result = validar_uploads(
        [_MagicFakeUpload("script.exe", b"MZ")]  # type: ignore[list-item]
    )
    assert result is not None
    assert "não permitido" in result


def test_validar_uploads_ainda_rejeita_content_type_divergente() -> None:
    result = validar_uploads(
        [
            _MagicFakeUploadFull(
                "foto.jpg",
                b"\xff\xd8\xffABC",
                content_type="application/pdf",
            )  # type: ignore[list-item]
        ]
    )
    assert result is not None
    assert "Conteúdo" in result


def test_validar_uploads_content_type_vazio_nao_bloqueia() -> None:
    result = validar_uploads(
        [
            _MagicFakeUploadFull(
                "foto.jpg",
                b"\xff\xd8\xffABC",
                content_type="",
            )  # type: ignore[list-item]
        ]
    )
    assert result is None


def test_validar_uploads_arquivo_sem_tamanho_detecta() -> None:
    class _NoSizeUpload(_MagicFakeUpload):
        @property
        def size(self) -> None:  # type: ignore[override]
            return None

    result = validar_uploads(
        [_NoSizeUpload("foto.jpg", b"\xff\xd8\xffABC")]  # type: ignore[list-item]
    )
    assert result is None


def test_uploaded_file_path_url_fora_prefixo() -> None:
    assert uploaded_file_path("/outra/rota/foto.jpg") is None


def test_uploaded_file_path_url_valida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_ui = tmp_path / "ui"
    uploads_dir = fake_ui / "static" / "uploads"
    uploads_dir.mkdir(parents=True)
    expected = uploads_dir / "veiculos" / "1" / "foto.jpg"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"dados")

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.upload_paths.ui_dir", fake_ui
    )

    result = uploaded_file_path("/static/uploads/veiculos/1/foto.jpg")
    assert result == expected
    assert result.is_file()


def test_uploaded_file_path_bloqueia_traversal_relativo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_ui = tmp_path / "ui"
    (fake_ui / "static" / "uploads").mkdir(parents=True)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.upload_paths.ui_dir", fake_ui
    )

    assert uploaded_file_path("/static/uploads/../../etc/passwd") is None


def test_uploaded_file_path_bloqueia_traversal_dotdot_meio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_ui = tmp_path / "ui"
    (fake_ui / "static" / "uploads").mkdir(parents=True)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.upload_paths.ui_dir", fake_ui
    )

    assert (
        uploaded_file_path("/static/uploads/veiculos/1/../../../../etc/hosts") is None
    )


def test_uploaded_file_path_bloqueia_escapar_via_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_ui = tmp_path / "ui"
    uploads_dir = fake_ui / "static" / "uploads"
    uploads_dir.mkdir(parents=True)
    externo = tmp_path / "fora" / "segredo.txt"
    externo.parent.mkdir(parents=True)
    externo.write_bytes(b"dados_secretos")
    link = uploads_dir / "link_escapando"
    os.symlink(externo, link)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.upload_paths.ui_dir", fake_ui
    )

    assert uploaded_file_path("/static/uploads/link_escapando") is None


def test_static_upload_exige_login(
    make_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_ui = tmp_path / "ui"
    upload = fake_ui / "static" / "uploads" / "veiculos" / "1" / "foto.jpg"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"imagem")
    monkeypatch.setattr("xtreme_system.api.setup._ui_dir", fake_ui)

    client = make_client()

    response = client.get("/static/uploads/veiculos/1/foto.jpg", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/login"


def test_static_upload_autenticado_retorna_arquivo(
    make_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_ui = tmp_path / "ui"
    upload = fake_ui / "static" / "uploads" / "veiculos" / "1" / "foto.jpg"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"imagem")
    monkeypatch.setattr("xtreme_system.api.setup._ui_dir", fake_ui)
    client = make_client(usuarios=[("admin", usuario.Papel.admin)])
    client.post(
        "/ui/login",
        data={"username": "admin", "password": "senha"},
        follow_redirects=False,
    )

    response = client.get("/static/uploads/veiculos/1/foto.jpg")

    assert response.status_code == 200
    assert response.content == b"imagem"


def test_static_asset_publico_continua_aberto(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client()

    response = client.get("/static/app.css")

    assert response.status_code == 200
