"""Exportação/importação completa de dados em /ui/configuracoes."""

import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from xtreme_system.database import core as database
from xtreme_system.exportacao import core as exportacao
from xtreme_system.usuario import core as usuario


@pytest.fixture(autouse=True)
def isolated_restore_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        database, "_restore_lock_path", lambda: tmp_path / "restore.lock"
    )


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
        timeout: int,
    ) -> subprocess.CompletedProcess[bytes]:
        assert capture_output is True
        assert check is False
        assert timeout == 300
        Path(cmd[-1]).write_bytes(b"dump")
        chamadas.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb"
        ),
    )
    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    assert exportacao.dump_database() == b"dump"
    assert chamadas[0][0][:-1] == [
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
        "-f",
    ]
    assert chamadas[0][0][-1].endswith(".dump")
    assert chamadas[0][1]["PGPASSWORD"] == "secret"


_TOC_TABELAS_ESSENCIAIS = "\n".join(
    f"{i}; 1259 0 TABLE public {tabela} postgres"
    for i, tabela in enumerate(("usuario", "veiculo", "cliente", "venda", "compra"))
).encode()


def test_restore_database_usa_pg_restore_com_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    chamadas: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        capture_output: bool,
        check: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[bytes]:
        assert capture_output is True
        assert check is False
        assert timeout == 300
        chamadas.append(cmd)
        if cmd[0] == "pg_restore" and "--list" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=_TOC_TABELAS_ESSENCIAIS, stderr=b""
            )
        assert env is not None
        assert env["PGPASSWORD"] == "secret"
        if cmd[0] == "pg_dump":
            Path(cmd[-1]).write_bytes(b"backup")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb",
            backup_dir=str(tmp_path),
        ),
    )
    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    exportacao.restore_database(b"dump")

    chamadas_restore = [
        c for c in chamadas if c[0] == "pg_restore" and "--list" not in c
    ]
    assert chamadas_restore[0][:-1] == [
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
    backups = list(tmp_path.glob("pre_restore_*.dump"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"backup"


def test_restore_database_rejeita_dump_sem_tabelas_essenciais(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    def fake_run(
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        capture_output: bool,
        check: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[bytes]:
        assert env is None
        assert capture_output is True
        assert check is False
        assert timeout == 300
        assert cmd[0] == "pg_restore"
        assert "--list" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb",
            backup_dir=str(tmp_path),
        ),
    )
    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    with pytest.raises(exportacao.ExportacaoError, match="tabelas ausentes"):
        exportacao.restore_database(b"dump")

    assert list(tmp_path.glob("pre_restore_*.dump")) == []


def test_restore_database_timeout_releases_restore_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    def fake_run(
        cmd: list[str],
        *,
        timeout: int,
        **_: object,
    ) -> subprocess.CompletedProcess[bytes]:
        assert cmd[0] == "pg_restore"
        assert "--list" in cmd
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb",
            backup_dir=str(tmp_path),
        ),
    )
    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    with pytest.raises(exportacao.ExportacaoError, match="tempo limite"):
        exportacao.restore_database(b"dump")

    with database.database_restore_lock():
        pass


def test_restore_database_rejeita_execucao_sobreposta() -> None:
    with (
        database.database_restore_lock(),
        pytest.raises(exportacao.RestoreEmAndamentoError, match="andamento"),
    ):
        exportacao.restore_database(b"dump")


def test_ui_rejeita_trafego_durante_restore(client: TestClient) -> None:
    _login(client)

    with database.database_restore_lock():
        resp = client.get("/ui/configuracoes")

    assert resp.status_code == 503
    assert "restaurado" in resp.text


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


def test_comandos_pg_incluem_stderr_redigido_no_erro(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stderr = b"could not connect to server at host=internal-db password=secret"

    monkeypatch.setattr(
        exportacao,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql+psycopg://user:secret@db:5433/appdb",
            backup_dir=str(tmp_path),
        ),
    )

    def fake_run(
        cmd: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=stderr)

    monkeypatch.setattr("xtreme_system.exportacao.core.subprocess.run", fake_run)

    with pytest.raises(exportacao.ExportacaoError) as dump_error:
        exportacao.dump_database_to_file(tmp_path / "dump.dump")
    assert "Não foi possível exportar o banco de dados." in str(dump_error.value)
    assert "internal-db" in str(dump_error.value)
    assert "password=[redacted]" in str(dump_error.value)
    assert "password=secret" not in str(dump_error.value)

    with pytest.raises(exportacao.ExportacaoError) as restore_error:
        exportacao.restore_database(b"dump")
    assert "Arquivo de backup inválido." in str(restore_error.value)
    assert "internal-db" in str(restore_error.value)
    assert "password=[redacted]" in str(restore_error.value)
    assert "password=secret" not in str(restore_error.value)

    monkeypatch.setattr(exportacao, "_validar_dump", lambda _: None)
    monkeypatch.setattr(exportacao, "_salvar_backup_pre_restore", lambda: None)
    with pytest.raises(exportacao.ExportacaoError) as restore_command_error:
        exportacao.restore_database_from_file(tmp_path / "dump.dump")
    assert "Não foi possível restaurar o banco de dados." in str(
        restore_command_error.value
    )
    assert "internal-db" in str(restore_command_error.value)
    assert "password=[redacted]" in str(restore_command_error.value)
    assert "password=secret" not in str(restore_command_error.value)


def test_ui_configuracoes_exportar_baixa_dump(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    def fake_dump(output_path: str | Path) -> None:
        Path(output_path).write_bytes(b"dump")

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.exportacao.dump_database_to_file",
        fake_dump,
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

    def fake_restore(dump_path: str | Path) -> None:
        recebidos.append(Path(dump_path).read_bytes())

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.exportacao.restore_database_from_file",
        fake_restore,
    )

    resp = client.post(
        "/ui/configuracoes/importar",
        files={"arquivo": ("backup.dump", b"dump", "application/octet-stream")},
    )

    assert resp.status_code == 200
    assert recebidos == [b"dump"]
    assert "Dados importados com sucesso." in resp.text


def test_ui_configuracoes_importar_renderiza_erro_de_restore(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    def fake_restore(_dump_path: str | Path) -> None:
        raise exportacao.ExportacaoError("dump corrompido")

    monkeypatch.setattr(exportacao, "restore_database_from_file", fake_restore)

    resp = client.post(
        "/ui/configuracoes/importar",
        files={"arquivo": ("backup.dump", b"dump", "application/octet-stream")},
    )

    assert resp.status_code == 200
    assert "dump corrompido" in resp.text


def test_ui_configuracoes_importar_rejeita_restore_concorrente(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    def fake_restore(_dump_path: str | Path) -> None:
        raise exportacao.RestoreEmAndamentoError

    monkeypatch.setattr(exportacao, "restore_database_from_file", fake_restore)

    resp = client.post(
        "/ui/configuracoes/importar",
        files={"arquivo": ("backup.dump", b"dump", "application/octet-stream")},
    )

    assert resp.status_code == 409
    assert "Já existe uma restauração do banco em andamento." in resp.text


def test_ui_configuracoes_importar_aceita_dump_maior_que_20mb(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    recebidos: list[bytes] = []

    def fake_restore(dump_path: str | Path) -> None:
        recebidos.append(Path(dump_path).read_bytes())

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.exportacao.restore_database_from_file",
        fake_restore,
    )

    dump = b"x" * (21 * 1024 * 1024)
    resp = client.post(
        "/ui/configuracoes/importar",
        files={"arquivo": ("backup.dump", dump, "application/octet-stream")},
    )

    assert resp.status_code == 200
    assert recebidos == [dump]


def test_ui_configuracoes_importar_roda_restore_em_threadpool(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)
    chamadas: list[tuple[Any, tuple[Any, ...]]] = []

    def fake_restore(dump_path: str | Path) -> None:
        assert Path(dump_path).read_bytes() == b"dump"

    async def fake_run_in_threadpool(func: Any, *args: Any) -> None:
        chamadas.append((func, args))
        func(*args)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.exportacao.restore_database_from_file",
        fake_restore,
    )
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.configuracoes.run_in_threadpool",
        fake_run_in_threadpool,
    )

    resp = client.post(
        "/ui/configuracoes/importar",
        files={"arquivo": ("backup.dump", b"dump", "application/octet-stream")},
    )

    assert resp.status_code == 200
    assert chamadas[0][0] is fake_restore
    assert Path(chamadas[0][1][0]).suffix == ".dump"
