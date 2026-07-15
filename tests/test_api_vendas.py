"""API vendas: CRUD via TestClient."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.api.core import app
from xtreme_system.database.core import get_session
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


def test_venda_concluida_marca_veiculo_vendido(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["veiculo"]["status"] == "vendido"
    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.status_code == 200
    assert veiculo.json()["status"] == "vendido"


def test_atualizar_venda_sincroniza_status_do_veiculo(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    venda = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "pendente",
        },
        headers=headers,
    )
    assert venda.status_code == 201, venda.text
    venda_id = venda.json()["id"]

    concluida = client.patch(
        f"/vendas/{venda_id}",
        json={"status": "concluido"},
        headers=headers,
    )
    assert concluida.status_code == 200
    assert concluida.json()["veiculo"]["status"] == "vendido"

    cancelada = client.patch(
        f"/vendas/{venda_id}",
        json={"status": "cancelado"},
        headers=headers,
    )
    assert cancelada.status_code == 200
    assert cancelada.json()["veiculo"]["status"] == "disponivel"
    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.status_code == 200
    assert veiculo.json()["status"] == "disponivel"


def test_atualizar_venda_concluida_para_pendente_libera_veiculo(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    venda = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda.status_code == 201, venda.text

    pendente = client.patch(
        f"/vendas/{venda.json()['id']}",
        json={"status": "pendente"},
        headers=headers,
    )

    assert pendente.status_code == 200
    assert pendente.json()["veiculo"]["status"] == "disponivel"
    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.status_code == 200
    assert veiculo.json()["status"] == "disponivel"


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


def test_cria_venda_para_veiculo_vendido_retorna_409(client: TestClient) -> None:
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
            "status": "concluido",
        },
        headers=headers,
    )

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
        headers=headers,
    )
    assert resp.status_code == 409
    assert "indisponível" in resp.json()["detail"]


def test_atualizar_venda_para_veiculo_indisponivel_retorna_409(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    inv_id = client.get("/investidores", headers=headers).json()[0]["id"]
    vei2 = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Civic",
            "cor": "Preto",
            "ano": 2020,
            "placa": "XYZ9G87",
            "km": 10000,
            "preco": "80000.00",
            "investidor_id": inv_id,
        },
        headers=headers,
    )
    assert vei2.status_code == 201
    veiculo2_id = vei2.json()["id"]

    client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo2_id,
            "data_venda": "2026-07-01",
            "valor_venda": "80000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )

    venda = client.post(
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
    assert venda.status_code == 201, venda.text
    venda_id = venda.json()["id"]

    resp = client.patch(
        f"/vendas/{venda_id}",
        json={"veiculo_id": veiculo2_id},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "indisponível" in resp.json()["detail"]


def test_deletar_venda_concluida_restaura_status_veiculo(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    venda = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda.status_code == 201

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "vendido"

    resp = client.delete(f"/vendas/{venda.json()['id']}", headers=headers)
    assert resp.status_code == 204

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "disponivel"


def test_deletar_venda_mantem_veiculo_vendido_se_ha_outra_concluida(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    venda1 = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "pendente",
        },
        headers=headers,
    )
    assert venda1.status_code == 201

    venda2 = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-02",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "pendente",
        },
        headers=headers,
    )
    assert venda2.status_code == 201

    client.patch(
        f"/vendas/{venda1.json()['id']}",
        json={"status": "concluido"},
        headers=headers,
    )
    client.patch(
        f"/vendas/{venda2.json()['id']}",
        json={"status": "concluido"},
        headers=headers,
    )

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "vendido"

    resp = client.delete(f"/vendas/{venda1.json()['id']}", headers=headers)
    assert resp.status_code == 204

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "vendido"


def test_deletar_venda_pendente_mantem_veiculo_disponivel(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    venda = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "pendente",
        },
        headers=headers,
    )
    assert venda.status_code == 201
    assert venda.json()["veiculo"]["status"] == "disponivel"

    resp = client.delete(f"/vendas/{venda.json()['id']}", headers=headers)
    assert resp.status_code == 204

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "disponivel"
