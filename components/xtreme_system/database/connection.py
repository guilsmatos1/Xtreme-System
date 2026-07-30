"""Lazy database engine and session-factory creation."""

from functools import lru_cache

import structlog
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from xtreme_system.database.core import get_settings

logger = structlog.get_logger(__name__)


def _build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    primary = _build_engine(settings.database_url)
    if not settings.database_url_fallback:
        return primary

    try:
        with primary.connect():
            pass
    except OperationalError:
        logger.warning(
            "database_primary_unreachable_using_fallback",
            database_url_fallback=settings.database_url_fallback,
        )
        primary.dispose()
        return _build_engine(settings.database_url_fallback)
    return primary


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
