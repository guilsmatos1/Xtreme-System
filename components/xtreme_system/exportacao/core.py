"""Exportação/importação do banco via pg_dump / pg_restore."""

import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from xtreme_system.database.core import (
    DatabaseRestoreInProgressError,
    database_restore_lock,
    get_settings,
)

_POSTGRES_REQUIRED = "Exportação/importação exige DATABASE_URL PostgreSQL"
_DUMP_FAILED = "Não foi possível exportar o banco de dados."
_RESTORE_FAILED = "Não foi possível restaurar o banco de dados."
_INVALID_BACKUP = "Arquivo de backup inválido."
_TABELAS_ESSENCIAIS = frozenset({"usuario", "veiculo", "cliente", "venda", "compra"})
_PG_COMMAND_TIMEOUT_SECONDS = 300


class ExportacaoError(Exception):
    """Falha ao executar pg_dump ou pg_restore."""


class RestoreEmAndamentoError(ExportacaoError):
    """Outra restauração já está usando o banco."""

    def __init__(self) -> None:
        super().__init__("Já existe uma restauração do banco em andamento.")


def _pg_conn_params() -> dict[str, str]:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("postgresql"):
        raise ExportacaoError(_POSTGRES_REQUIRED)
    return {
        "host": url.host or "localhost",
        "port": str(url.port or 5432),
        "user": url.username or "postgres",
        "password": url.password or "",
        "dbname": url.database or "xtreme",
    }


def _pg_args() -> list[str]:
    p = _pg_conn_params()
    return ["-h", p["host"], "-p", p["port"], "-U", p["user"], "-d", p["dbname"]]


def _pg_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = _pg_conn_params()["password"]
    return env


def _run_pg_command(
    cmd: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # noqa: S603
            cmd,
            env=env,
            capture_output=True,
            check=False,
            timeout=_PG_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        command = Path(cmd[0]).name
        raise ExportacaoError(  # noqa: TRY003
            f"{command} excedeu o tempo limite de "
            f"{_PG_COMMAND_TIMEOUT_SECONDS} segundos."
        ) from exc


def dump_database_to_file(output_path: str | Path) -> None:
    cmd = ["pg_dump", *_pg_args(), "-Fc", "-Z", "6", "-f", str(output_path)]
    result = _run_pg_command(cmd, env=_pg_env())
    if result.returncode != 0:
        raise ExportacaoError(_DUMP_FAILED)


def dump_database() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
    try:
        dump_database_to_file(tmp_path)
        return Path(tmp_path).read_bytes()
    finally:
        os.unlink(tmp_path)


def _listar_tabelas_do_dump(tmp_path: str) -> set[str]:
    cmd = ["pg_restore", "--list", tmp_path]
    result = _run_pg_command(cmd)
    if result.returncode != 0:
        raise ExportacaoError(_INVALID_BACKUP)
    tabelas = set()
    for linha in result.stdout.decode(errors="replace").splitlines():
        partes = linha.split()
        if "TABLE" in partes and "public" in partes:
            idx = partes.index("public")
            if idx + 1 < len(partes):
                tabelas.add(partes[idx + 1])
    return tabelas


def _validar_dump(tmp_path: str) -> None:
    tabelas = _listar_tabelas_do_dump(tmp_path)
    faltando = sorted(_TABELAS_ESSENCIAIS - tabelas)
    if faltando:
        raise ExportacaoError(  # noqa: TRY003
            "Arquivo não parece ser um backup válido do xtreme-system "
            f"(tabelas ausentes: {', '.join(faltando)})."
        )


def _salvar_backup_pre_restore() -> None:
    backup_dir = Path(get_settings().backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dump_database_to_file(backup_dir / f"pre_restore_{ts}.dump")


def restore_database_from_file(dump_path: str | Path) -> None:
    try:
        with database_restore_lock():
            dump_path = Path(dump_path)
            _validar_dump(str(dump_path))
            _salvar_backup_pre_restore()
            cmd = [
                "pg_restore",
                *_pg_args(),
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                "--single-transaction",
                str(dump_path),
            ]
            result = _run_pg_command(cmd, env=_pg_env())
            if result.returncode != 0:
                raise ExportacaoError(_RESTORE_FAILED)
    except DatabaseRestoreInProgressError as exc:
        raise RestoreEmAndamentoError from exc


def restore_database(dump: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        f.write(dump)
        tmp_path = f.name
    try:
        restore_database_from_file(tmp_path)
    finally:
        os.unlink(tmp_path)
