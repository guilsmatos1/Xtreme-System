"""Health check: GET /health sem auth, pingando o banco."""

from collections.abc import Callable, Iterator
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from xtreme_system.api.core import app
from xtreme_system.database.core import get_session


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def test_health_retorna_ok_sem_auth(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "database": "ok",
        "database_target": "primary",
    }


def test_raiz_redireciona_para_dashboard_ui(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/ui/dashboard"


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
            "database_target": "primary",
        }
    finally:
        app.dependency_overrides.clear()
