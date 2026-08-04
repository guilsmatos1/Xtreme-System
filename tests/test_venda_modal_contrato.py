"""Modal de contrato de venda (/ui/vendas/{id}/contrato/modal e /processar)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario


def _seed_perfis_restritos(session: Session) -> None:
    actor_id = session.info["usuario_id"]
    perfil_sem_acesso = perfil.create(
        session,
        perfil.PerfilCreate(nome="Vendas sem contrato", paginas=["vendas"]),
        actor_id,
    )
    perfil_so_baixar = perfil.create(
        session,
        perfil.PerfilCreate(
            nome="Vendas so baixar contrato",
            paginas=["vendas"],
            restricoes={"vendas": {"operacoes": ["baixar_contrato"]}},
        ),
        actor_id,
    )
    usuario.create(
        session,
        usuario.UsuarioCreate(
            username="sem-contrato",
            senha="senha",
            papel=usuario.Papel.funcionario,
            perfil_id=perfil_sem_acesso.id,
        ),
        actor_id,
    )
    usuario.create(
        session,
        usuario.UsuarioCreate(
            username="so-baixar",
            senha="senha",
            papel=usuario.Papel.funcionario,
            perfil_id=perfil_so_baixar.id,
        ),
        actor_id,
    )


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=_seed_perfis_restritos,
    )


def _admin_headers(client: TestClient) -> dict[str, str]:
    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _login_ui(
    client: TestClient,
    username: str = "admin",
    password: str = "senha",  # noqa: S107
) -> None:
    resp = client.post(
        "/ui/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert resp.status_code == 303


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


def test_modal_contrato_com_documento_mostra_preview_e_botoes(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)
    assert client.post(f"/ui/vendas/{venda_id}/contrato/processar").status_code == 200

    resp = client.get(f"/ui/vendas/{venda_id}/contrato/modal")

    assert resp.status_code == 200
    body = resp.text
    assert 'class="pdf-preview"' in body
    assert "Contrato ainda não gerado" not in body
    assert ">Baixar<" in body or "Baixar" in body
    assert "Reprocessar" in body


def test_modal_contrato_sem_documento_mostra_processar(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)

    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.vendas.documento_contrato_venda.list_by_venda",
        lambda _session, _venda_id: [],
    )

    resp = client.get(f"/ui/vendas/{venda_id}/contrato/modal")

    assert resp.status_code == 200
    body = resp.text
    assert 'class="pdf-preview"' not in body
    assert "Contrato ainda não gerado" in body
    assert "Reprocessar" not in body
    assert "Processar" in body


def test_processar_contrato_gera_pdf_e_retorna_modal_com_preview(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)
    assert client.post(f"/ui/vendas/{venda_id}/contrato/processar").status_code == 200

    url_antiga = client.get(
        f"/ui/vendas/{venda_id}/contrato", headers=headers, follow_redirects=False
    ).headers["location"]

    resp = client.post(f"/ui/vendas/{venda_id}/contrato/processar")

    assert resp.status_code == 200
    body = resp.text
    assert 'class="pdf-preview"' in body
    assert "Reprocessar" in body

    url_nova = client.get(
        f"/ui/vendas/{venda_id}/contrato", headers=headers, follow_redirects=False
    ).headers["location"]
    assert url_nova != url_antiga


def test_modal_contrato_exige_permissao_baixar_contrato(client: TestClient) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)
    client.cookies.clear()

    _login_ui(client, "sem-contrato", "senha")

    resp = client.get(f"/ui/vendas/{venda_id}/contrato/modal")
    assert resp.status_code == 403

    resp = client.post(f"/ui/vendas/{venda_id}/contrato/processar")
    assert resp.status_code == 403


def test_modal_contrato_sem_editar_oculta_reprocessar_e_bloqueia_processar(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    _login_ui(client)
    venda_id = _seed_venda(client, headers)
    assert client.post(f"/ui/vendas/{venda_id}/contrato/processar").status_code == 200
    client.cookies.clear()

    _login_ui(client, "so-baixar", "senha")

    resp = client.get(f"/ui/vendas/{venda_id}/contrato/modal")
    assert resp.status_code == 200
    body = resp.text
    assert 'class="pdf-preview"' in body
    assert "Reprocessar" not in body
    assert "Baixar" in body

    resp = client.post(f"/ui/vendas/{venda_id}/contrato/processar")
    assert resp.status_code == 403
