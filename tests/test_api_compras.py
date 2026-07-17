"""API compras: CRUD via TestClient."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.api.core import app
from xtreme_system.database.core import get_session
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="admin", senha="senha", papel=usuario.Papel.admin
            ),
        )
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="vendedor", senha="senha", papel=usuario.Papel.funcionario
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


def test_admin_crud_compras(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    create_resp = client.post(
        "/compras",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-01",
            "valor_compra": "35000.00",
            "debitos": "500.00",
            "observacoes": "compra com débitos",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    compra_id = create_resp.json()["id"]
    assert create_resp.json()["valor_compra"] == "35000.00"
    assert create_resp.json()["cliente"]["nome"] == "João Silva"
    assert create_resp.json()["veiculo"]["modelo"] == "Gol"

    list_resp = client.get("/compras", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/compras/{compra_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == compra_id

    update_resp = client.patch(
        f"/compras/{compra_id}",
        json={"valor_compra": "36000.00", "observacoes": "ajustada"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["valor_compra"] == "36000.00"
    assert update_resp.json()["observacoes"] == "ajustada"

    delete_resp = client.delete(f"/compras/{compra_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/compras/{compra_id}", headers=headers)
    assert missing_resp.status_code == 404


def test_vendedor_nao_cria_compra(client: TestClient) -> None:
    admin_headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    vendedor_headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    cliente_id, veiculo_id = _seed(client, admin_headers)

    resp = client.post(
        "/compras",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-01",
            "valor_compra": "35000.00",
        },
        headers=vendedor_headers,
    )
    assert resp.status_code == 403


def test_api_compras_respeita_perfil_em_leitura_e_mutacao(
    client: TestClient,
) -> None:
    admin_headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, admin_headers)
    create_resp = client.post(
        "/compras",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-01",
            "valor_compra": "35000.00",
            "debitos": "500.00",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201

    session = next(app.dependency_overrides[get_session]())
    p = perfil.create(
        session,
        perfil.PerfilCreate(
            nome="Compras limitado",
            paginas=["compras"],
            restricoes={
                "compras": {
                    "campos_ocultos": ["valor_compra", "debitos"],
                    "operacoes": ["cadastrar"],
                }
            },
        ),
    )
    vendedor = usuario.get_by_username(session, "vendedor")
    assert vendedor is not None
    vendedor.perfil_id = p.id
    session.flush()

    vendedor_headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    list_resp = client.get("/compras", headers=vendedor_headers)
    assert list_resp.status_code == 200
    assert "valor_compra" not in list_resp.json()[0]
    assert "debitos" not in list_resp.json()[0]

    nova_compra = client.post(
        "/compras",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-02",
            "valor_compra": "36000.00",
        },
        headers=vendedor_headers,
    )
    assert nova_compra.status_code == 201
    assert "valor_compra" not in nova_compra.json()

    update_resp = client.patch(
        f"/compras/{create_resp.json()['id']}",
        json={"observacoes": "bloqueado"},
        headers=vendedor_headers,
    )
    assert update_resp.status_code == 403


def test_compra_cliente_inexistente_retorna_400(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    _, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/compras",
        json={
            "cliente_id": 9999,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-01",
            "valor_compra": "35000.00",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "cliente_id" in resp.json()["detail"]
