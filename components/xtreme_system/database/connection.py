"""Lazy database engine and session-factory creation."""

from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import Literal

import structlog
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from xtreme_system.database.core import get_settings

logger = structlog.get_logger(__name__)

DatabaseTarget = Literal["primary", "fallback"]
_engine_state_lock = Lock()


@dataclass
class _EngineState:
    fallback_engine: Engine | None = None
    fallback_database_url: str | None = None
    active_database_target: DatabaseTarget = "primary"


_engine_state = _EngineState()


def _build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


@lru_cache
def _get_primary_engine(database_url: str) -> Engine:
    return _build_engine(database_url)


def _dispose_fallback_engine() -> None:
    if _engine_state.fallback_engine is not None:
        _engine_state.fallback_engine.dispose()
    _engine_state.fallback_engine = None
    _engine_state.fallback_database_url = None


def get_database_target() -> DatabaseTarget:
    with _engine_state_lock:
        return _engine_state.active_database_target


def get_engine() -> Engine:
    settings = get_settings()
    primary = _get_primary_engine(settings.database_url)
    fallback_url = settings.database_url_fallback

    with _engine_state_lock:
        if not fallback_url:
            _dispose_fallback_engine()
            _engine_state.active_database_target = "primary"
            return primary

        try:
            with primary.connect():
                pass
        except OperationalError:
            logger.exception(
                "database_primary_unreachable_using_fallback",
                database_url_fallback=fallback_url,
            )
            primary.dispose()

            if _engine_state.fallback_database_url != fallback_url:
                _dispose_fallback_engine()
                _engine_state.fallback_database_url = fallback_url
                _engine_state.fallback_engine = _build_engine(fallback_url)
            elif _engine_state.fallback_engine is None:
                _engine_state.fallback_engine = _build_engine(fallback_url)

            try:
                with _engine_state.fallback_engine.connect():
                    pass
            except OperationalError:
                logger.exception(
                    "database_fallback_unreachable",
                    database_url_fallback=fallback_url,
                )
                _dispose_fallback_engine()
                raise
            _engine_state.active_database_target = "fallback"
            return _engine_state.fallback_engine

        if _engine_state.active_database_target == "fallback":
            _dispose_fallback_engine()
        _engine_state.active_database_target = "primary"
        return primary


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def clear_engine_cache() -> None:
    """Reset cached engines for tests and controlled process reconfiguration."""
    with _engine_state_lock:
        _dispose_fallback_engine()
        _engine_state.active_database_target = "primary"
        _get_primary_engine.cache_clear()
