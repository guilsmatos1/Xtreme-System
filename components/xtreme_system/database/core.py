"""Configuração de banco: settings, engine, sessão e Base declarativa."""

from collections.abc import Callable, Iterator
from functools import lru_cache

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = structlog.get_logger(__name__)

_POST_COMMIT_KEY = "_post_commit_callbacks"
_POST_ROLLBACK_KEY = "_post_rollback_callbacks"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/xtreme"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class Base(DeclarativeBase):
    pass


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
