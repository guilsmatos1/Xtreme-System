"""Configuração de banco: settings, engine, sessão e Base declarativa."""

import time
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Protocol

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    JSON,
    Column,
    String,
    Table,
    create_engine,
    delete,
    event,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = structlog.get_logger(__name__)

_POST_COMMIT_KEY = "_post_commit_callbacks"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/xtreme"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class Base(DeclarativeBase):
    pass


rate_limit_state = Table(
    "rate_limit_state",
    Base.metadata,
    Column("bucket", String(255), primary_key=True),
    Column("hits", JSON, nullable=False),
)


class RateLimiterStore(Protocol):
    def allow(
        self, bucket: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]: ...

    def reset(self) -> None: ...


class DatabaseRateLimiterStore:
    def __init__(self, bind: Engine | None = None) -> None:
        self._bind = bind or engine

    def allow(
        self, bucket: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]:
        now = time.time()
        cutoff = now - window_seconds
        with self._bind.begin() as conn:
            self._ensure_bucket(conn, bucket)
            hits = self._load_hits(conn, bucket)
            hits = [hit for hit in hits if hit >= cutoff]
            if len(hits) >= limit:
                retry_after = window_seconds - (now - hits[0])
                self._save_hits(conn, bucket, hits)
                return False, retry_after
            hits.append(now)
            self._save_hits(conn, bucket, hits)
            return True, 0.0

    def reset(self) -> None:
        with self._bind.begin() as conn:
            conn.execute(delete(rate_limit_state))

    def _ensure_bucket(self, conn: Connection, bucket: str) -> None:
        statement = insert(rate_limit_state).values(bucket=bucket, hits=[])
        if conn.dialect.name == "postgresql":
            statement = pg_insert(rate_limit_state).values(bucket=bucket, hits=[])
            statement = statement.on_conflict_do_nothing(index_elements=["bucket"])
        elif conn.dialect.name == "sqlite":
            statement = sqlite_insert(rate_limit_state).values(bucket=bucket, hits=[])
            statement = statement.on_conflict_do_nothing(index_elements=["bucket"])
        else:
            statement = statement.prefix_with("OR IGNORE")
        conn.execute(statement)

    def _load_hits(self, conn: Connection, bucket: str) -> list[float]:
        result = conn.execute(
            select(rate_limit_state.c.hits)
            .where(rate_limit_state.c.bucket == bucket)
            .with_for_update()
        ).scalar_one()
        return [float(hit) for hit in result]

    def _save_hits(self, conn: Connection, bucket: str, hits: list[float]) -> None:
        conn.execute(
            update(rate_limit_state)
            .where(rate_limit_state.c.bucket == bucket)
            .values(hits=hits)
        )


engine = create_engine(
    get_settings().database_url, future=True, pool_pre_ping=True, pool_recycle=1800
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_rollback")
def _drop_post_commit_on_rollback(session: Session) -> None:
    session.info.pop(_POST_COMMIT_KEY, None)


def register_post_commit(session: Session, callback: Callable[[], None]) -> None:
    callbacks = session.info.setdefault(_POST_COMMIT_KEY, [])
    callbacks.append(callback)


def _invoke_post_commit(session: Session) -> None:
    callbacks: list[Callable[[], None]] = session.info.pop(_POST_COMMIT_KEY, [])
    for cb in callbacks:
        try:
            cb()
        except Exception:
            logger.warning("post_commit_callback_failed", exc_info=True)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
        _invoke_post_commit(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
