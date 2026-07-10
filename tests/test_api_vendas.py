"""API vendas: CRUD via TestClient."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from xtreme_system.api.core import app
from xtreme_system.database.core import Base, get_session
from xtreme_system.usuario import core as usuario


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="admin", senha="senha", papel=usuario.Papel.admin
            ),
        )
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="vendedor", senha="senha", papel=usuario.Papel.vendedor
            ),
        )

        def override() -> Iterator[Session]:
            yield session

        app.dependency_overrides[get_session] = override
        yield TestClient(app)
        app.dependency_overrides.clear()


def _token(client: TestClient, username: str) -> str:
    resp = client.post("/login", data={"username": username, "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def _seed(client: TestClient, headers: dict[str, str]) -> tuple[int, int]:
    """Cria investidor, cliente e veiculo."""
    inv_id = client.post("/investidores", json={"nome": "Ana"}, headers=headers).json()[
        "id"
    ]
    cli = client.post(
        "/clientes",
        json={
            "nome": "João Silva",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert cli.status_code == 201
    cliente_id = cli.json()["id"]
    vei = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Gol",
            "cor": "Branco",
            "ano": 2018,
            "placa": "ABC1D23",
            "km": 50000,
            "preco": "40000.00",
            "investidor_id": inv_id,
        },
        headers=headers,
    )
    assert vei.status_code == 201
    veiculo_id = vei.json()["id"]
    return cliente_id, veiculo_id


def test_admin_cria_venda(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "valor_entrada": "10000.00",
            "forma_pagamento": "financiamento",
            "parcelas": 36,
            "status": "pendente",
            "observacoes": "aguardando aprovação",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["valor_venda"] == "40000.00"
    assert data["status"] == "pendente"
    assert data["cliente"]["nome"] == "João Silva"
    assert data["veiculo"]["modelo"] == "Gol"


def test_admin_lista_vendas(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
        },
        headers=headers,
    )

    resp = client.get("/vendas", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_vendedor_nao_cria_venda(client: TestClient) -> None:
    admin_headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    vendedor_headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    cliente_id, veiculo_id = _seed(client, admin_headers)

    resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
        },
        headers=vendedor_headers,
    )
    assert resp.status_code == 403


def test_cliente_inexistente_retorna_400(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    _, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas",
        json={
            "cliente_id": 9999,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "cliente_id" in resp.json()["detail"]
