"""Exportação/importação completa de dados em /ui/configuracoes."""

import subprocess
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from xtreme_system.exportacao import core as exportacao
from xtreme_system.usuario import core as usuario


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(usuarios=[("admin", usuario.Papel.admin)])


def _login(client: TestClient) -> None:
    resp = client.post("/ui/login", data={"username": "admin", "password": "senha"})
    assert resp.status_code == 200


def test_dump_database_usa_pg_dump_custom_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(
        cmd: list[str],
        *,
        env: dict[str, str],
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        assert capture_output is True
        assert check is False
        chamadas.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, stdout=b"dump", stderr=b"")

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb"
        ),
    )
    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    assert exportacao.dump_database() == b"dump"
    assert chamadas[0][0] == [
        "pg_dump",
        "-h",
        "db",
        "-p",
        "5433",
        "-U",
        "user",
        "-d",
        "appdb",
        "-Fc",
        "-Z",
        "6",
    ]
    assert chamadas[0][1]["PGPASSWORD"] == "secret"


def test_restore_database_usa_pg_restore_com_replace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        *,
        env: dict[str, str],
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        assert capture_output is True
        assert check is False
        chamadas.append(cmd)
        assert env["PGPASSWORD"] == "secret"
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb"
        ),
    )
    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    exportacao.restore_database(b"dump")

    assert chamadas[0][:-1] == [
        "pg_restore",
        "-h",
        "db",
        "-p",
        "5433",
        "-U",
        "user",
        "-d",
        "appdb",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--single-transaction",
    ]


def test_dump_database_rejeita_database_url_nao_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(database_url="sqlite:///:memory:"),
    )

    with pytest.raises(exportacao.ExportacaoError):
        exportacao.dump_database()


def test_ui_configuracoes_exportar_baixa_dump(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.exportacao.dump_database",
        lambda: b"dump",
    )

    resp = client.post("/ui/configuracoes/exportar")

    assert resp.status_code == 200
    assert resp.content == b"dump"
    assert resp.headers["content-type"] == "application/octet-stream"
    assert "humpback_dump_" in resp.headers["content-disposition"]


def test_ui_configuracoes_importar_restaura_dump(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    recebidos: list[bytes] = []
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.exportacao.restore_database",
        recebidos.append,
    )

    resp = client.post(
        "/ui/configuracoes/importar",
        files={"arquivo": ("backup.dump", b"dump", "application/octet-stream")},
    )

    assert resp.status_code == 200
    assert recebidos == [b"dump"]
    assert "Dados importados com sucesso." in resp.text
