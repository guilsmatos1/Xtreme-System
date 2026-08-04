"""API vendas: CRUD via TestClient."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.core import app
from xtreme_system.database.core import get_session
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda_core
from xtreme_system.venda import status_veiculo
from xtreme_system.workflow.core import (
    validate_veiculo_disponivel_para_venda,
    validate_venda_update,
)


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


def test_recomputar_status_de_veiculo_bloqueia_linha() -> None:
    session = Mock(spec=Session)
    session.get.return_value = SimpleNamespace(status=veiculo.StatusVeiculo.disponivel)

    status_veiculo.recomputar_status_veiculo_por_vendas(session, 123)

    session.get.assert_called_once_with(veiculo.Veiculo, 123, with_for_update=True)


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
    assert vei.json()["investidor_id"] == inv_id
    assert vei.json()["criado_em"]
    veiculo_id = vei.json()["id"]
    return cliente_id, veiculo_id


def _criar_veiculo(
    client: TestClient,
    headers: dict[str, str],
    investidor_id: int,
    *,
    modelo: str,
    placa: str,
) -> int:
    resp = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": modelo,
            "cor": "Prata",
            "ano": 2019,
            "placa": placa,
            "km": 30000,
            "preco": "50000.00",
            "investidor_id": investidor_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


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
    assert data["cliente_id"] == cliente_id
    assert data["veiculo_id"] == veiculo_id
    assert data["cliente"]["nome"] == "João Silva"
    assert data["veiculo"]["modelo"] == "Gol"
    assert data["vendedor"]["username"] == "admin"


def test_venda_rejeita_valores_financeiros_e_operacionais_impossiveis(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "valor_entrada": "40000.01",
            "debitos": "-0.01",
            "km": -1,
            "forma_pagamento": "a_vista",
            "parcelas": 0,
            "valor_pendente": "-0.01",
        },
        headers=headers,
    )

    assert resp.status_code == 422


def test_criar_venda_rejeita_pagamento_pendente_sem_valor_positivo(
    client: TestClient,
) -> None:
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
            "pagamento_pendente": True,
            "datas_pagamento": "10/08/2026",
        },
        headers=headers,
    )

    assert resp.status_code == 422
    assert "valor_pendente" in resp.text


def test_criar_venda_rejeita_valor_pendente_sem_pagamento_pendente(
    client: TestClient,
) -> None:
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
            "valor_pendente": "1000.00",
        },
        headers=headers,
    )

    assert resp.status_code == 422
    assert "pagamento_pendente" in resp.text


def test_atualizar_venda_rejeita_entrada_maior_que_valor_salvo(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    venda_resp = client.post(
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
    assert venda_resp.status_code == 201

    resp = client.patch(
        f"/vendas/{venda_resp.json()['id']}",
        json={"valor_entrada": "40000.01"},
        headers=headers,
    )

    assert resp.status_code == 400
    assert "valor_entrada" in resp.json()["detail"]


def test_atualizar_venda_rejeita_valor_pendente_sem_pagamento_pendente_salvo(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    venda_resp = client.post(
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
    assert venda_resp.status_code == 201

    resp = client.patch(
        f"/vendas/{venda_resp.json()['id']}",
        json={"valor_pendente": "1000.00"},
        headers=headers,
    )

    assert resp.status_code == 400
    assert "pagamento_pendente" in resp.json()["detail"]


def test_api_json_respeita_perfil_em_veiculos_e_vendas(
    client: TestClient,
) -> None:
    admin_headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, admin_headers)
    venda_resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "45000.00",
            "valor_entrada": "5000.00",
            "forma_pagamento": "financiamento",
            "parcelas": 36,
        },
        headers=admin_headers,
    )
    assert venda_resp.status_code == 201

    session = next(app.dependency_overrides[get_session]())
    p = perfil.create(
        session,
        perfil.PerfilCreate(
            nome="Vendas limitado",
            paginas=["veiculos", "vendas"],
            restricoes={
                "veiculos": {"campos_ocultos": ["preco", "investidor"]},
                "vendas": {"campos_ocultos": ["valor_venda", "valor_entrada"]},
            },
        ),
    )
    vendedor = usuario.get_by_username(session, "vendedor")
    assert vendedor is not None
    vendedor.perfil_id = p.id
    session.flush()

    vendedor_headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    veiculos_resp = client.get("/veiculos", headers=vendedor_headers)
    assert veiculos_resp.status_code == 200
    assert "preco" not in veiculos_resp.json()[0]
    assert "investidor" not in veiculos_resp.json()[0]

    vendas_resp = client.get("/vendas", headers=vendedor_headers)
    assert vendas_resp.status_code == 200
    assert "valor_venda" not in vendas_resp.json()[0]
    assert "valor_entrada" not in vendas_resp.json()[0]
    assert vendas_resp.json()[0]["cliente"]["nome"] == "João Silva"


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


def test_atualizar_unica_venda_concluida_para_pendente_reserva_veiculo(
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
    assert pendente.json()["veiculo"]["status"] == "reservado"
    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.status_code == 200
    assert veiculo.json()["status"] == "reservado"


def test_venda_concluida_disponibiliza_veiculo_de_troca(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_troca_id = _criar_veiculo(
        client,
        headers,
        investidor_id,
        modelo="Onix",
        placa="TRC1D23",
    )

    venda_anterior = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_troca_id,
            "data_venda": "2026-06-01",
            "valor_venda": "50000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda_anterior.status_code == 201, venda_anterior.text

    troca_vendida = client.get(f"/veiculos/{veiculo_troca_id}", headers=headers)
    assert troca_vendida.json()["status"] == "vendido"

    venda_com_troca = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "veiculo_troca_id": veiculo_troca_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )

    assert venda_com_troca.status_code == 201, venda_com_troca.text
    assert venda_com_troca.json()["veiculo_troca"]["status"] == "disponivel"
    troca_disponivel = client.get(f"/veiculos/{veiculo_troca_id}", headers=headers)
    assert troca_disponivel.json()["status"] == "disponivel"


def test_cancelar_venda_com_troca_recomputa_status_do_veiculo_de_troca(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_troca_id = _criar_veiculo(
        client,
        headers,
        investidor_id,
        modelo="HB20",
        placa="TRC4D56",
    )

    venda_anterior = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_troca_id,
            "data_venda": "2026-06-01",
            "valor_venda": "50000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda_anterior.status_code == 201, venda_anterior.text

    venda_com_troca = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "veiculo_troca_id": veiculo_troca_id,
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda_com_troca.status_code == 201, venda_com_troca.text

    cancelada = client.patch(
        f"/vendas/{venda_com_troca.json()['id']}",
        json={"status": "cancelado"},
        headers=headers,
    )

    assert cancelada.status_code == 200, cancelada.text
    troca = client.get(f"/veiculos/{veiculo_troca_id}", headers=headers)
    assert troca.json()["status"] == "vendido"


def test_atualizar_venda_pendente_preserva_veiculo_reservado(
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
    assert venda.status_code == 201, venda.text

    reservado = client.patch(
        f"/veiculos/{veiculo_id}",
        json={"status": "reservado"},
        headers=headers,
    )
    assert reservado.status_code == 200

    atualizada = client.patch(
        f"/vendas/{venda.json()['id']}",
        json={"observacoes": "aguardando documento"},
        headers=headers,
    )

    assert atualizada.status_code == 200
    assert atualizada.json()["veiculo"]["status"] == "reservado"
    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "reservado"


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


def test_validacao_de_venda_bloqueia_linha_do_veiculo() -> None:
    session = Mock(spec=Session)
    session.get.return_value = SimpleNamespace(status=veiculo.StatusVeiculo.disponivel)

    validate_veiculo_disponivel_para_venda(session, 123)

    session.get.assert_called_once_with(veiculo.Veiculo, 123, with_for_update=True)


def test_validacao_de_atualizacao_de_venda_bloqueia_veiculo_atual() -> None:
    session = Mock(spec=Session)
    session.get.return_value = SimpleNamespace(status=veiculo.StatusVeiculo.vendido)
    venda_obj = cast(
        venda_core.Venda,
        SimpleNamespace(
            veiculo_id=123,
            valor_venda=40000,
            valor_entrada=None,
            pagamento_pendente=False,
            valor_pendente=None,
            datas_pagamento=None,
        ),
    )
    data = venda_core.VendaUpdate.model_validate({"observacoes": "ajuste"})

    validate_venda_update(session, venda_obj, data)

    session.get.assert_called_once_with(veiculo.Veiculo, 123, with_for_update=True)


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


def test_venda_concluida_nao_pode_ser_duplicada_por_veiculo(
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
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda1.status_code == 201

    session = next(app.dependency_overrides[get_session]())
    session.commit()
    with pytest.raises(IntegrityError):
        venda_core.create(
            session,
            venda_core.VendaCreate(
                cliente_id=cliente_id,
                veiculo_id=veiculo_id,
                data_venda="2026-07-02",
                valor_venda="40000.00",
                forma_pagamento="a_vista",
                parcelas=1,
                status=venda_core.StatusVenda.concluido,
            ),
        )
    session.rollback()
    assert (
        session.query(venda_core.Venda)
        .filter_by(veiculo_id=veiculo_id, status=venda_core.StatusVenda.concluido)
        .count()
        == 1
    )


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
    assert venda.json()["veiculo"]["status"] == "reservado"

    resp = client.delete(f"/vendas/{venda.json()['id']}", headers=headers)
    assert resp.status_code == 204

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "disponivel"


def test_deletar_venda_pendente_preserva_veiculo_indisponivel_manual(
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
    assert venda.json()["veiculo"]["status"] == "reservado"

    indisponivel = client.patch(
        f"/veiculos/{veiculo_id}",
        json={"status": "indisponivel"},
        headers=headers,
    )
    assert indisponivel.status_code == 200

    resp = client.delete(f"/vendas/{venda.json()['id']}", headers=headers)
    assert resp.status_code == 204

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "indisponivel"


def test_atualizar_venda_concluida_para_pendente_reserva_veiculo(
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
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda1.status_code == 201
    venda1_id = venda1.json()["id"]

    resp = client.patch(
        f"/vendas/{venda1_id}",
        json={"status": "pendente"},
        headers=headers,
    )
    assert resp.status_code == 200

    veiculo = client.get(f"/veiculos/{veiculo_id}", headers=headers)
    assert veiculo.json()["status"] == "reservado"
