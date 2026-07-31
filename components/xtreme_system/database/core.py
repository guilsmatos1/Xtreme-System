"""Database settings, declarative base, and request session lifecycle."""

import hashlib
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from fcntl import LOCK_EX, LOCK_NB, LOCK_SH, LOCK_UN, flock
from functools import lru_cache
from pathlib import Path

import structlog
from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import event, inspect
from sqlalchemy.orm import DeclarativeBase, Session

logger = structlog.get_logger(__name__)

_POST_COMMIT_KEY = "_post_commit_callbacks"
_POST_ROLLBACK_KEY = "_post_rollback_callbacks"


class DatabaseRestoreInProgressError(RuntimeError):
    """The database is currently being restored or another guard is active."""


def _restore_lock_path() -> Path:
    database_url = get_settings().database_url
    key = hashlib.sha256(database_url.encode()).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"xtreme-system-restore-{key}.lock"


@contextmanager
def _database_lock(*, exclusive: bool) -> Iterator[None]:
    lock_path = _restore_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        lock_type = LOCK_EX if exclusive else LOCK_SH
        try:
            flock(lock_file.fileno(), lock_type | LOCK_NB)
        except BlockingIOError as exc:
            raise DatabaseRestoreInProgressError from exc
        try:
            yield
        finally:
            flock(lock_file.fileno(), LOCK_UN)


@contextmanager
def database_traffic_lock() -> Iterator[None]:
    """Allow a request only while no database restore owns the lock."""

    with _database_lock(exclusive=False):
        yield


@contextmanager
def database_restore_lock() -> Iterator[None]:
    """Own the database exclusively for one restore operation."""

    with _database_lock(exclusive=True):
        yield


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/xtreme"
    database_url_fallback: str | None = None
    backup_dir: str = "backups"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class Base(DeclarativeBase):
    pass


def SessionLocal() -> Session:  # noqa: N802
    from xtreme_system.database.connection import get_session_factory  # noqa: PLC0415

    return get_session_factory()()


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


def invoke_post_commit(session: Session) -> None:
    callbacks: list[Callable[[], None]] = session.info.pop(_POST_COMMIT_KEY, [])
    session.info.pop(_POST_ROLLBACK_KEY, None)
    for cb in callbacks:
        try:
            cb()
        except Exception:
            logger.warning("post_commit_callback_failed", exc_info=True)


_READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_REQUEST_SESSION_ATTR = "db_session"
_REQUEST_SESSION_DETACHED_ATTR = "db_session_detached"


def _should_commit_session(request: Request) -> bool:
    return request.method.upper() not in _READ_ONLY_METHODS


def bind_request_session(request: Request) -> Session:
    session = SessionLocal()
    setattr(request.state, _REQUEST_SESSION_ATTR, session)
    return session


def detach_request_session(request: Request, *, keep: Sequence[object] = ()) -> None:
    """End the request transaction before an external database operation.

    ``pg_dump`` and ``pg_restore`` need the request's database connection to be
    released. Objects in ``keep`` are loaded and expunged first so they remain
    usable after the session is detached. Request finalization skips this
    session because this function has already rolled it back and closed it.
    """
    session = getattr(request.state, _REQUEST_SESSION_ATTR, None)
    if session is None:
        return
    for obj in keep:
        state = inspect(obj)
        if state is None:
            raise TypeError
        for attr in state.mapper.column_attrs:
            getattr(obj, attr.key)
        session.expunge(obj)
    session.rollback()
    session.close()
    setattr(request.state, _REQUEST_SESSION_DETACHED_ATTR, True)


def finish_request_session(
    request: Request, error: BaseException | None = None
) -> None:
    if getattr(request.state, _REQUEST_SESSION_DETACHED_ATTR, False):
        delattr(request.state, _REQUEST_SESSION_DETACHED_ATTR)
        return
    session = getattr(request.state, _REQUEST_SESSION_ATTR, None)
    if session is None:
        return
    try:
        if error is not None:
            session.rollback()
        elif _should_commit_session(request):
            session.commit()
            invoke_post_commit(session)
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        delattr(request.state, _REQUEST_SESSION_ATTR)


def get_session(request: Request) -> Iterator[Session]:
    request_session = getattr(request.state, _REQUEST_SESSION_ATTR, None)
    if request_session is not None:
        yield request_session
        return

    session = SessionLocal()
    try:
        yield session
        if _should_commit_session(request):
            session.commit()
            invoke_post_commit(session)
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
