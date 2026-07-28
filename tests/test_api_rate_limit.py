"""Rate limiting: tentativas de login e requests gerais da API."""

import time as time_module
from collections.abc import Callable
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from xtreme_system.api.setup import (
    _GERAL_LIMIT,
    _LOGIN_LIMIT,
    _MemoryRateLimiterStore,
    reset_rate_limiters,
)
from xtreme_system.database.rate_limit import DatabaseRateLimiterStore, rate_limit_state
from xtreme_system.usuario import core as usuario


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


def test_login_rate_limit_ignora_x_forwarded_for_spoof(
    make_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")
    client = make_client(client_addr=("198.51.100.2", 50000))
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
    assert resp.status_code == 429


def test_login_rate_limit_usa_x_forwarded_for_de_proxy_confiavel(
    make_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")
    client = make_client(client_addr=("172.18.0.2", 50000))
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

    reset_rate_limiters()

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


def _token(client: TestClient, username: str) -> str:
    resp = client.post("/login", data={"username": username, "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def test_requests_gerais_autenticadas_limitam_por_usuario(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(
        usuarios=[
            ("ana", usuario.Papel.admin),
            ("bia", usuario.Papel.admin),
        ]
    )
    ana_headers = {"Authorization": f"Bearer {_token(client, 'ana')}"}
    bia_headers = {"Authorization": f"Bearer {_token(client, 'bia')}"}

    for _ in range(_GERAL_LIMIT):
        resp = client.get("/investidores", headers=ana_headers)
        assert resp.status_code == 200

    resp = client.get("/investidores", headers=ana_headers)
    assert resp.status_code == 429

    resp = client.get("/investidores", headers=bia_headers)
    assert resp.status_code == 200


def test_rate_limit_respeita_x_forwarded_for(
    make_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")
    client = make_client(client_addr=("172.18.0.2", 50000))
    ip_a = {"X-Forwarded-For": "203.0.113.10"}
    ip_b = {"X-Forwarded-For": "203.0.113.11"}

    for _ in range(_GERAL_LIMIT):
        resp = client.get("/investidores", headers=ip_a)
        assert resp.status_code == 401

    resp = client.get("/investidores", headers=ip_a)
    assert resp.status_code == 429

    resp = client.get("/investidores", headers=ip_b)
    assert resp.status_code == 401


def test_rate_limit_ignora_x_forwarded_for_de_proxy_nao_confiavel(
    make_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "172.18.0.0/16")
    client = make_client(client_kwargs={"client": ("10.0.0.2", 123)})

    for indice in range(_GERAL_LIMIT):
        resp = client.get(
            "/investidores", headers={"X-Forwarded-For": f"203.0.113.{indice}"}
        )
        assert resp.status_code == 401

    resp = client.get("/investidores", headers={"X-Forwarded-For": "203.0.113.200"})
    assert resp.status_code == 429


def test_memory_rate_limiter_limpa_buckets_antigos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryRateLimiterStore()
    times = iter([100.0, 300.0])
    monkeypatch.setattr(time_module, "time", lambda: next(times))

    assert store.allow("antigo", limit=1, window_seconds=60) == (True, 0.0)
    assert store.allow("novo", limit=1, window_seconds=60) == (True, 0.0)

    assert list(vars(store)["_hits"]) == ["novo"]


def test_database_rate_limiter_usa_contador_por_janela(db_session: Session) -> None:
    store = DatabaseRateLimiterStore(cast(Engine, db_session.get_bind()))

    assert store.allow("203.0.113.10", limit=2, window_seconds=60) == (True, 0.0)
    assert store.allow("203.0.113.10", limit=2, window_seconds=60) == (True, 0.0)

    allowed, retry_after = store.allow("203.0.113.10", limit=2, window_seconds=60)

    assert allowed is False
    assert retry_after > 0
    row = db_session.execute(select(rate_limit_state)).mappings().one()
    assert row["bucket"] == "203.0.113.10"
    assert row["hit_count"] == 2


def test_database_rate_limiter_limpa_buckets_antigos(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = cast(Engine, db_session.get_bind())
    store = DatabaseRateLimiterStore(engine)
    times = iter([100.0, 300.0])
    monkeypatch.setattr(time_module, "time", lambda: next(times))

    assert store.allow("antigo", limit=1, window_seconds=60) == (True, 0.0)
    assert store.allow("novo", limit=1, window_seconds=60) == (True, 0.0)

    buckets = db_session.execute(select(rate_limit_state.c.bucket)).scalars().all()
    assert buckets == ["novo"]
