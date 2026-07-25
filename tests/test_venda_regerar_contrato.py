"""Regeração do PDF do contrato de venda (/ui/vendas/{id}/contrato/regerar)."""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_documento_contrato_venda import _extract_pdf_text
from xtreme_system.usuario import core as usuario


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(usuarios=[("admin", usuario.Papel.admin)])


def _admin_headers(client: TestClient) -> dict[str, str]:
    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _login_ui(client: TestClient) -> None:
    resp = client.post("/ui/login", data={"username": "admin", "password": "senha"})
    assert resp.status_code == 200


def _seed_venda(client: TestClient, headers: dict[str, str]) -> int:
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
    payload: dict[str, Any] = {
        "cliente_id": str(cliente_id),
        "veiculo_id": str(veiculo_id),
        "data_venda": "2026-07-01",
        "valor_venda": "40000.00",
        "forma_pagamento": "a_vista",
        "parcelas": "1",
        "status": "pendente",
    }
    resp = client.post("/ui/vendas", data=payload)
    assert resp.status_code == 200
    vendas = client.get("/vendas", headers=headers).json()
    assert vendas, resp.text
    return int(vendas[0]["id"])


def _caminho(url: str) -> Path:
    return Path("bases/xtreme_system/api").joinpath(url.lstrip("/"))


def test_regerar_contrato_cria_novo_arquivo_com_layout_atual(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)

    original = client.get(
        f"/ui/vendas/{venda_id}/contrato", headers=headers, follow_redirects=False
    )
    url_original = original.headers["location"]

    resp = client.post(
        f"/ui/vendas/{venda_id}/contrato/regerar",
        headers=headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303

    atualizado = client.get(
        f"/ui/vendas/{venda_id}/contrato", headers=headers, follow_redirects=False
    )
    url_novo = atualizado.headers["location"]

    assert url_novo != url_original
    caminho_novo = _caminho(url_novo)
    assert caminho_novo.read_bytes().startswith(b"%PDF")


def test_baixar_contrato_usa_documento_mais_recente_por_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.vendas.documento_contrato_venda.list_by_venda",
        lambda _session, _venda_id: [
            SimpleNamespace(id=2, url="/static/uploads/contrato-novo.pdf"),
            SimpleNamespace(id=1, url="/static/uploads/contrato-antigo.pdf"),
        ],
    )

    resp = client.get(
        f"/ui/vendas/{venda_id}/contrato", headers=headers, follow_redirects=False
    )

    assert resp.headers["location"] == "/static/uploads/contrato-novo.pdf"


def test_regerar_contrato_reflete_dados_atualizados_da_empresa(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)

    empresa_resp = client.post(
        "/ui/configuracoes/empresa",
        data={"nome": "Nova Razão Social", "cidade": "Sao Paulo"},
    )
    assert empresa_resp.status_code == 200

    client.post(f"/ui/vendas/{venda_id}/contrato/regerar", headers=headers)
    url = client.get(
        f"/ui/vendas/{venda_id}/contrato", headers=headers, follow_redirects=False
    ).headers["location"]
    texto = _extract_pdf_text(_caminho(url).read_bytes())
    assert "Nova Razão Social" in texto
