import os
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.database import create_test_engine
from xtreme_system.api.setup import reset_rate_limiters


def pytest_configure() -> None:
    # Garante segredo JWT em ambientes sem .env (ex.: pre-commit, CI) antes
    # do lru_cache de get_settings() ser populado por qualquer rota de login.
    os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key")


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    # limiters são module-level; sem reset um teste consome o limite do
    # próximo (TestClient sempre usa o mesmo IP).
    reset_rate_limiters()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sessão isolada com schema migrado em Postgres ou SQLite local."""
    engine = create_test_engine()
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with maker() as session:
        yield session
    engine.dispose()
