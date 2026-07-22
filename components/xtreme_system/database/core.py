"""Configuração de banco: settings, engine, sessão e Base declarativa."""

import time
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Protocol

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    Column,
    Float,
    Integer,
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
_POST_ROLLBACK_KEY = "_post_rollback_callbacks"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/xtreme"
    backup_dir: str = "backups"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class Base(DeclarativeBase):
    pass


rate_limit_state = Table(
    "rate_limit_state",
    Base.metadata,
    Column("bucket", String(255), primary_key=True),
    Column("window_started_at", Float, nullable=False),
    Column("hit_count", Integer, nullable=False),
    Column("updated_at", Float, nullable=False),
)


class RateLimiterStore(Protocol):
    def allow(
        self, bucket: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]: ...

    def reset(self) -> None: ...


class DatabaseRateLimiterStore:
    def __init__(self, bind: Engine | None = None) -> None:
        self._bind = bind or engine
        self._last_cleanup = 0.0

    def allow(
        self, bucket: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]:
        now = time.time()
        cutoff = now - window_seconds
        with self._bind.begin() as conn:
            self._cleanup_old_buckets(conn, now, window_seconds)
            for _ in range(2):
                if self._increment_current_window(conn, bucket, limit, cutoff, now):
                    return True, 0.0
                if self._reset_expired_window(conn, bucket, cutoff, now):
                    return True, 0.0
                if self._insert_bucket(conn, bucket, now):
                    return True, 0.0

            row = (
                conn.execute(
                    select(rate_limit_state.c.window_started_at).where(
                        rate_limit_state.c.bucket == bucket
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return True, 0.0
            retry_after = window_seconds - (now - row["window_started_at"])
            return False, max(retry_after, 0.0)

    def reset(self) -> None:
        with self._bind.begin() as conn:
            conn.execute(delete(rate_limit_state))

    def _cleanup_old_buckets(
        self, conn: Connection, now: float, window_seconds: float
    ) -> None:
        cleanup_interval = max(window_seconds, 60.0)
        if now - self._last_cleanup < cleanup_interval:
            return
        self._last_cleanup = now
        conn.execute(
            delete(rate_limit_state).where(
                rate_limit_state.c.updated_at < now - (window_seconds * 2)
            )
        )

    def _increment_current_window(
        self, conn: Connection, bucket: str, limit: int, cutoff: float, now: float
    ) -> bool:
        return bool(
            conn.execute(
                update(rate_limit_state)
                .where(rate_limit_state.c.bucket == bucket)
                .where(rate_limit_state.c.window_started_at > cutoff)
                .where(rate_limit_state.c.hit_count < limit)
                .values(
                    hit_count=rate_limit_state.c.hit_count + 1,
                    updated_at=now,
                )
            ).rowcount
        )

    def _reset_expired_window(
        self, conn: Connection, bucket: str, cutoff: float, now: float
    ) -> bool:
        return bool(
            conn.execute(
                update(rate_limit_state)
                .where(rate_limit_state.c.bucket == bucket)
                .where(rate_limit_state.c.window_started_at <= cutoff)
                .values(window_started_at=now, hit_count=1, updated_at=now)
            ).rowcount
        )

    def _insert_bucket(self, conn: Connection, bucket: str, now: float) -> bool:
        statement = insert(rate_limit_state).values(
            bucket=bucket,
            window_started_at=now,
            hit_count=1,
            updated_at=now,
        )
        if conn.dialect.name == "postgresql":
            statement = pg_insert(rate_limit_state).values(
                bucket=bucket,
                window_started_at=now,
                hit_count=1,
                updated_at=now,
            )
            statement = statement.on_conflict_do_nothing(index_elements=["bucket"])
        elif conn.dialect.name == "sqlite":
            statement = sqlite_insert(rate_limit_state).values(
                bucket=bucket,
                window_started_at=now,
                hit_count=1,
                updated_at=now,
            )
            statement = statement.on_conflict_do_nothing(index_elements=["bucket"])
        else:
            statement = statement.prefix_with("OR IGNORE")
        return bool(conn.execute(statement).rowcount)


engine = create_engine(
    get_settings().database_url, future=True, pool_pre_ping=True, pool_recycle=1800
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_rollback")
def _drop_post_commit_on_rollback(session: Session) -> None:
    session.info.pop(_POST_COMMIT_KEY, None)
    callbacks: list[Callable[[], None]] = session.info.pop(_POST_ROLLBACK_KEY, [])
    for cb in callbacks:
        try:
            cb()
        except Exception:
            logger.warning("post_rollback_callback_failed", exc_info=True)


def register_post_commit(session: Session, callback: Callable[[], None]) -> None:
    callbacks = session.info.setdefault(_POST_COMMIT_KEY, [])
    callbacks.append(callback)


def register_post_rollback(session: Session, callback: Callable[[], None]) -> None:
    callbacks = session.info.setdefault(_POST_ROLLBACK_KEY, [])
    callbacks.append(callback)


def _invoke_post_commit(session: Session) -> None:
    callbacks: list[Callable[[], None]] = session.info.pop(_POST_COMMIT_KEY, [])
    session.info.pop(_POST_ROLLBACK_KEY, None)
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
