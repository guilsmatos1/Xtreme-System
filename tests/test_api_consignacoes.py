"""API consignações: CRUD via TestClient."""

from collections.abc import Callable
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xtreme_system.api.routes.ui_routes import consignacoes as consignacoes_ui
from xtreme_system.consignacao import core as consignacao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[
            ("admin", usuario.Papel.admin),
            ("vendedor", usuario.Papel.funcionario),
        ]
    )


def _token(client: TestClient, username: str) -> str:
    resp = client.post("/login", data={"username": username, "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def test_atualizacao_de_status_da_consignacao_bloqueia_linha_do_veiculo() -> None:
    session = Mock(spec=Session)
    session.get.return_value = veiculo.Veiculo(status=veiculo.StatusVeiculo.cancelado)
    consignacao_obj = consignacao.Consignacao(
        veiculo_id=123,
        status=consignacao.StatusConsignacao.ativa,
    )

    consignacoes_ui._sincronizar_status_veiculo_consignacao(session, consignacao_obj)  # noqa: SLF001

    session.get.assert_called_once_with(veiculo.Veiculo, 123, with_for_update=True)


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


def test_admin_lista_consignacoes_com_paginacao(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/consignacoes",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "valor_venda": "45000.00",
            "comissao_percentual": "5.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["valor_venda"] == "45000.00"
    assert data["comissao_percentual"] == "5.00"
    assert data["status"] == "ativa"

    resp_list = client.get("/consignacoes", headers=headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) == 1
