"""Helpers for test database bootstrap."""

import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url

from xtreme_system.database.connection import clear_engine_cache
from xtreme_system.database.core import Base, get_settings
from xtreme_system.fechamento_venda import core as _fechamento_venda  # noqa: F401

# URLs já migrados neste processo. DROP SCHEMA + alembic upgrade head só é
# necessário uma vez por processo de teste; chamadas seguintes apenas
# truncam as tabelas, que é ordens de magnitude mais rápido.
_migrated_urls: set[str] = set()
_sqlite_test_database_urls: dict[str, str] = {}


def _worker_schema() -> str:
    """Schema Postgres isolado por worker do pytest-xdist.

    Sem xdist (`PYTEST_XDIST_WORKER` ausente) usa `public`, mantendo o
    comportamento anterior. Cada worker migra/trunca seu próprio schema, o
    que evita que processos paralelos colidam num único `public`
    compartilhado.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    return f"test_{worker_id}" if worker_id else "public"


def _with_search_path(database_url: str, schema: str) -> str:
    if schema == "public":
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}options={quote(f'-c search_path={schema}')}"


def create_test_engine() -> Engine:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url:
        schema = _worker_schema()
        scoped_url = _with_search_path(database_url, schema)
        engine = create_engine(scoped_url, future=True)
        if scoped_url not in _migrated_urls:
            _reset_postgres_schema(engine, schema)
            _run_migrations(scoped_url)
            _migrated_urls.add(scoped_url)
        # Sempre trunca, mesmo logo após migrar: a migração `seed_default_admin`
        # insere um usuário "admin" real (bootstrap de produção), então um
        # schema recém-migrado não está vazio como os testes assumem. Sem
        # isto, o primeiro teste a tocar um schema por processo herda esse
        # "admin" pré-existente e falha com UsernameJaExisteError se tentar
        # criar o seu próprio — deterministicamente, mas só nesse teste, o
        # que lia como flakiness.
        _truncate_all_tables(engine)
        return engine

    if not os.environ.get("XTREME_ALLOW_SQLITE_TEST_DB"):
        msg = "TEST_DATABASE_URL is required unless XTREME_ALLOW_SQLITE_TEST_DB=1"
        raise RuntimeError(msg)

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "single")
    database_key = f"{os.getpid()}-{worker_id}"
    sqlite_test_database_url = _sqlite_test_database_urls.get(database_key)
    if sqlite_test_database_url is None:
        database_path = (
            Path(tempfile.gettempdir())
            / f"xtreme-system-test-{os.getpid()}-{worker_id}.sqlite3"
        )
        database_path.unlink(missing_ok=True)
        sqlite_test_database_url = f"sqlite:///{database_path}"
        _sqlite_test_database_urls[database_key] = sqlite_test_database_url
        os.environ["DATABASE_URL"] = sqlite_test_database_url
        get_settings.cache_clear()
        clear_engine_cache()

    engine = create_engine(
        sqlite_test_database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
    event.listen(
        engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


def _reset_postgres_schema(engine: Engine, schema: str) -> None:
    url = make_url(str(engine.url))
    if url.get_backend_name() != "postgresql":
        msg = "TEST_DATABASE_URL must use PostgreSQL"
        raise RuntimeError(msg)
    if url.database is None or "test" not in url.database.lower():
        msg = "Refusing to reset a non-test database"
        raise RuntimeError(msg)

    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))


def _truncate_all_tables(engine: Engine) -> None:
    table_names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )


def _run_migrations(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
