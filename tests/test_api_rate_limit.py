"""Rate limiting: tentativas de login e requests gerais da API."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from xtreme_system.api.setup import _GERAL_LIMIT, _LOGIN_LIMIT


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def test_login_bloqueia_apos_limite(client: TestClient) -> None:
    for _ in range(_LOGIN_LIMIT):
        resp = client.post("/login", data={"username": "x", "password": "x"})
        assert resp.status_code == 401

    resp = client.post("/login", data={"username": "x", "password": "x"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_login_rate_limit_isolates_clients_behind_proxy(
    client: TestClient,
) -> None:
    headers_a = {"X-Forwarded-For": "203.0.113.10"}
    headers_b = {"X-Forwarded-For": "203.0.113.11"}

    for _ in range(_LOGIN_LIMIT):
        resp = client.post(
            "/login", data={"username": "x", "password": "x"}, headers=headers_a
        )
        assert resp.status_code == 401

    resp = client.post(
        "/login", data={"username": "x", "password": "x"}, headers=headers_b
    )
    assert resp.status_code == 401


def test_login_rate_limit_nao_vaza_entre_clients(
    make_client: Callable[..., TestClient],
) -> None:
    with make_client() as client1:
        for _ in range(_LOGIN_LIMIT):
            resp = client1.post("/login", data={"username": "x", "password": "x"})
            assert resp.status_code == 401

        resp = client1.post("/login", data={"username": "x", "password": "x"})
        assert resp.status_code == 429

    with make_client() as client2:
        resp = client2.post("/login", data={"username": "x", "password": "x"})
        assert resp.status_code == 401


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


def test_rate_limit_respeita_x_forwarded_for(client: TestClient) -> None:
    ip_a = {"X-Forwarded-For": "203.0.113.10"}
    ip_b = {"X-Forwarded-For": "203.0.113.11"}

    for _ in range(_GERAL_LIMIT):
        resp = client.get("/investidores", headers=ip_a)
        assert resp.status_code == 401

    resp = client.get("/investidores", headers=ip_a)
    assert resp.status_code == 429

    resp = client.get("/investidores", headers=ip_b)
    assert resp.status_code == 401
