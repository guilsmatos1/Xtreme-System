"""Exportação/importação do banco via pg_dump / pg_restore."""

import os
import subprocess
import tempfile
from urllib.parse import urlparse

from xtreme_system.database.core import get_settings


class ExportacaoError(Exception):
    """Falha ao executar pg_dump ou pg_restore."""


def _pg_conn_params() -> dict[str, str]:
    url = get_settings().database_url
    if url.startswith("postgresql+"):
        url = "postgresql" + url[url.index("://") :]
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/") or "xtreme",
    }


def _pg_args() -> list[str]:
    p = _pg_conn_params()
    return ["-h", p["host"], "-p", p["port"], "-U", p["user"], "-d", p["dbname"]]


def _pg_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = _pg_conn_params()["password"]
    return env


def dump_database() -> bytes:
    cmd = ["pg_dump", *_pg_args(), "-Fc", "-Z", "6"]
    result = subprocess.run(cmd, env=_pg_env(), capture_output=True, check=False)  # noqa: S603
    if result.returncode != 0:
        stderr = result.stderr.decode() if result.stderr else "pg_dump falhou"
        raise ExportacaoError(stderr)
    return result.stdout


def restore_database(dump: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        f.write(dump)
        tmp_path = f.name
    try:
        cmd = [
            "pg_restore",
            *_pg_args(),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--single-transaction",
            tmp_path,
        ]
        result = subprocess.run(cmd, env=_pg_env(), capture_output=True, check=False)  # noqa: S603
        if result.returncode != 0:
            stderr = result.stderr.decode() if result.stderr else "pg_restore falhou"
            raise ExportacaoError(stderr)
    finally:
        os.unlink(tmp_path)
