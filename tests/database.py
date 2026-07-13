"""Helpers for test database bootstrap."""

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from xtreme_system.database.core import Base, get_settings


def create_test_engine() -> Engine:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url:
        engine = create_engine(database_url, future=True)
        _reset_postgres_schema(engine)
        _run_migrations(database_url)
        return engine

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(
        engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    return engine


def _reset_postgres_schema(engine: Engine) -> None:
    url = make_url(str(engine.url))
    if url.get_backend_name() != "postgresql":
        msg = "TEST_DATABASE_URL must use PostgreSQL"
        raise RuntimeError(msg)
    if url.database is None or "test" not in url.database.lower():
        msg = "Refusing to reset a non-test database"
        raise RuntimeError(msg)

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


def _run_migrations(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
