"""Health check: GET /health sem auth, pingando o banco."""

from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from xtreme_system.api.core import app
from xtreme_system.database.core import Base, get_session


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:

        def override() -> Iterator[Session]:
            yield session

        app.dependency_overrides[get_session] = override
        yield TestClient(app)
        app.dependency_overrides.clear()


def test_health_retorna_ok_sem_auth(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_health_degradado_quando_banco_indisponivel(client: TestClient) -> None:
    mock: Session = MagicMock(spec=Session)
    cast(Any, mock.execute).side_effect = SQLAlchemyError("indisponivel")

    def bad_session() -> Iterator[Session]:
        yield mock

    app.dependency_overrides[get_session] = bad_session
    try:
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json() == {
            "status": "degradado",
            "database": "indisponivel",
        }
    finally:
        app.dependency_overrides.clear()
