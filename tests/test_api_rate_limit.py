"""Rate limiting: tentativas de login e requests gerais da API."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from xtreme_system.api.core import app
from xtreme_system.api.setup import _GERAL_LIMIT, _LOGIN_LIMIT
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


def test_login_bloqueia_apos_limite(client: TestClient) -> None:
    for _ in range(_LOGIN_LIMIT):
        resp = client.post("/login", data={"username": "x", "password": "x"})
        assert resp.status_code == 401

    resp = client.post("/login", data={"username": "x", "password": "x"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_ui_login_bloqueia_apos_limite_e_retorna_html(client: TestClient) -> None:
    for _ in range(_LOGIN_LIMIT):
        client.post("/ui/login", data={"username": "x", "password": "x"})

    resp = client.post("/ui/login", data={"username": "x", "password": "x"})
    assert resp.status_code == 429
    assert "text/html" in resp.headers["content-type"]


def test_health_isento_de_rate_limit(client: TestClient) -> None:
    for _ in range(_GERAL_LIMIT + 5):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_requests_gerais_bloqueiam_apos_limite(client: TestClient) -> None:
    for _ in range(_GERAL_LIMIT):
        resp = client.get("/investidores")
        assert resp.status_code == 401

    resp = client.get("/investidores")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
