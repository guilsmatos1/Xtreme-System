"""CRUD do logo da empresa em /ui/configuracoes (aba Empresa)."""

import contextlib
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xtreme_system.usuario import core as usuario

_PNG = b"\x89PNG\r\n\x1a\n" + b"logo-de-teste"
_URL_LOGO = re.compile(r"/static/uploads/empresa/[a-f0-9]+\.png")


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    client = make_client(usuarios=[("admin", usuario.Papel.admin)])
    resp = client.post("/ui/login", data={"username": "admin", "password": "senha"})
    assert resp.status_code == 200
    return client


def _caminho(url: str) -> Path:
    return Path("bases/xtreme_system/api").joinpath(url.lstrip("/"))


def _enviar(client: TestClient, conteudo: bytes = _PNG) -> str:
    resp = client.post(
        "/ui/configuracoes/empresa/logo",
        files=[("logo", ("logo.png", conteudo, "image/png"))],
    )
    assert resp.status_code == 200
    match = _URL_LOGO.search(resp.text)
    assert match is not None, resp.text
    return match.group(0)


def _dados_empresa(**extra: str) -> dict[str, str]:
    return {"nome": "XTREME MOTORS", "cidade": "Sao Paulo", **extra}


def test_upload_logo_grava_arquivo_e_url(client: TestClient) -> None:
    url = _enviar(client)
    caminho = _caminho(url)
    try:
        assert caminho.read_bytes() == _PNG
    finally:
        with contextlib.suppress(FileNotFoundError):
            caminho.unlink()


def test_upload_logo_rejeita_pdf(client: TestClient) -> None:
    resp = client.post(
        "/ui/configuracoes/empresa/logo",
        files=[("logo", ("contrato.pdf", b"%PDF-x", "application/pdf"))],
    )
    assert resp.status_code == 200
    assert "deve ser uma imagem" in resp.text
    assert _URL_LOGO.search(resp.text) is None


def test_upload_logo_rejeita_assinatura_invalida(client: TestClient) -> None:
    resp = client.post(
        "/ui/configuracoes/empresa/logo",
        files=[("logo", ("logo.png", b"nao-e-png", "image/png"))],
    )
    assert resp.status_code == 200
    assert "Assinatura do arquivo" in resp.text
    assert _URL_LOGO.search(resp.text) is None


def test_upload_logo_substitui_e_apaga_o_anterior(client: TestClient) -> None:
    antigo = _caminho(_enviar(client))
    novo = _caminho(_enviar(client, _PNG + b"-v2"))
    try:
        assert antigo != novo
        assert not antigo.exists()
        assert novo.read_bytes() == _PNG + b"-v2"
    finally:
        for caminho in (antigo, novo):
            with contextlib.suppress(FileNotFoundError):
                caminho.unlink()


def test_excluir_logo_remove_arquivo_e_url(client: TestClient) -> None:
    caminho = _caminho(_enviar(client))
    try:
        resp = client.post("/ui/configuracoes/empresa/logo/excluir")
        assert resp.status_code == 200
        assert "Logo removido." in resp.text
        assert _URL_LOGO.search(resp.text) is None
        assert not caminho.exists()
    finally:
        with contextlib.suppress(FileNotFoundError):
            caminho.unlink()


def test_salvar_dados_da_empresa_preserva_o_logo(client: TestClient) -> None:
    url = _enviar(client)
    caminho = _caminho(url)
    try:
        resp = client.post("/ui/configuracoes/empresa", data=_dados_empresa())
        assert resp.status_code == 200
        assert url in resp.text
        assert caminho.exists()
    finally:
        with contextlib.suppress(FileNotFoundError):
            caminho.unlink()
