"""Health check: GET /health sem auth, pingando o banco."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


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


def test_health_degradado_quando_banco_indisponivel(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection.execute.side_effect = SQLAlchemyError("indisponivel")
    engine = MagicMock(spec=Engine)
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr("xtreme_system.api.routes.json.get_engine", lambda: engine)

    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {
        "status": "degradado",
        "database": "indisponivel",
        "database_target": "primary",
    }
    assert "health_check_database_unavailable" in caplog.text
    assert "indisponivel" in caplog.text
