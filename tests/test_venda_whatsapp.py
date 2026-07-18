"""Notificação de venda via WhatsApp: disparo best-effort no after_create."""

import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from xtreme_system.usuario import core as usuario
from xtreme_system.whatsapp import core as whatsapp


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[("admin", usuario.Papel.admin)], invoke_post_commit=True
    )


def _token(client: TestClient, username: str) -> str:
    resp = client.post("/login", data={"username": username, "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def _seed(client: TestClient, headers: dict[str, str]) -> tuple[int, int]:
    inv_id = client.post("/investidores", json={"nome": "Ana"}, headers=headers).json()[
        "id"
    ]
    cliente_id = client.post(
        "/clientes",
        json={
            "nome": "João Silva",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    ).json()["id"]
    veiculo_id = client.post(
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
    ).json()["id"]
    return cliente_id, veiculo_id


def _payload(cliente_id: int, veiculo_id: int) -> dict[str, Any]:
    return {
        "cliente_id": cliente_id,
        "veiculo_id": veiculo_id,
        "data_venda": "2026-07-01",
        "valor_venda": "40000.00",
        "forma_pagamento": "a_vista",
        "parcelas": 1,
    }


def _configurar(client: TestClient, mensagem_template: str = "") -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})
    client.post(
        "/ui/configuracoes",
        data={
            "evolution_api_url": "http://evolution:8080",
            "evolution_api_key": "chave",
            "evolution_instance": "xtreme-motors",
            "evolution_group_id": "1203630@g.us",
            "mensagem_template": mensagem_template,
        },
    )


def test_criar_venda_dispara_notificacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens: list[str] = []
    monkeypatch.setattr(
        whatsapp, "_enviar", lambda _config, texto: mensagens.append(texto)
    )
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    time.sleep(0.1)
    assert len(mensagens) == 1
    assert "João Silva" in mensagens[0]
    assert "Gol" in mensagens[0]


def test_falha_no_envio_nao_impede_criacao_da_venda(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _falha(_config: whatsapp.WhatsappConfig, _texto: str) -> None:
        raise OSError("Evolution API fora do ar")

    monkeypatch.setattr(whatsapp, "_enviar", _falha)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201


def test_configuracoes_salva_e_recarrega(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})

    resp = client.post(
        "/ui/configuracoes",
        data={
            "evolution_api_url": "http://evolution:8080",
            "evolution_api_key": "chave-secreta",
            "evolution_instance": "xtreme-motors",
            "evolution_group_id": "1203630@g.us",
        },
    )
    assert resp.status_code == 200
    assert "http://evolution:8080" in resp.text
    assert "1203630@g.us" in resp.text

    resp = client.get("/ui/configuracoes")
    assert resp.status_code == 200
    assert "xtreme-motors" in resp.text


def test_configuracoes_exige_admin(client: TestClient) -> None:
    resp = client.get("/ui/configuracoes", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui/login"


def test_notificacao_usa_template_customizado(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens: list[str] = []
    monkeypatch.setattr(
        whatsapp, "_enviar", lambda _config, texto: mensagens.append(texto)
    )
    _configurar(client, mensagem_template="Venda para {cliente} no valor de R$ {valor}")

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    time.sleep(0.1)
    assert mensagens == ["Venda para João Silva no valor de R$ 40000.00"]


def test_notificacao_ignora_placeholder_desconhecido(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens: list[str] = []
    monkeypatch.setattr(
        whatsapp, "_enviar", lambda _config, texto: mensagens.append(texto)
    )
    _configurar(client, mensagem_template="Olá {cliente}, código {inexistente}")

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    time.sleep(0.1)
    assert mensagens == ["Olá João Silva, código {inexistente}"]
