"""Perfil aplicado às rotas JSON geradas por factory."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from xtreme_system.api.core import app
from xtreme_system.database.core import get_session
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario


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


def _headers(client: TestClient, username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client, username)}"}


def _seed(client: TestClient, headers: dict[str, str]) -> dict[str, int]:
    investidor_id = client.post(
        "/investidores", json={"nome": "Ana"}, headers=headers
    ).json()["id"]
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
            "investidor_id": investidor_id,
        },
        headers=headers,
    ).json()["id"]
    venda_id = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-01",
            "valor_venda": "45000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
        },
        headers=headers,
    ).json()["id"]
    return {
        "investidor": investidor_id,
        "cliente": cliente_id,
        "veiculo": veiculo_id,
        "venda": venda_id,
    }


def _perfil_vendedor(
    nome: str, paginas: list[str], restricoes: dict[str, object]
) -> None:
    session = next(app.dependency_overrides[get_session]())
    p = perfil.create(
        session,
        perfil.PerfilCreate(nome=nome, paginas=paginas, restricoes=restricoes),
    )
    vendedor = usuario.get_by_username(session, "vendedor")
    assert vendedor is not None
    vendedor.perfil_id = p.id
    session.flush()


@pytest.mark.parametrize(
    ("pagina", "path", "campo_oculto"),
    [
        ("veiculos", "/veiculos", "preco"),
        ("vendas", "/vendas", "valor_venda"),
    ],
)
def test_api_factory_oculta_campos_por_perfil(
    client: TestClient, pagina: str, path: str, campo_oculto: str
) -> None:
    admin_headers = _headers(client, "admin")
    _seed(client, admin_headers)
    _perfil_vendedor(
        f"{pagina} limitado",
        [pagina],
        {pagina: {"campos_ocultos": [campo_oculto], "operacoes": []}},
    )

    resp = client.get(path, headers=_headers(client, "vendedor"))

    assert resp.status_code == 200
    assert campo_oculto not in resp.json()[0]
    assert campo_oculto in client.get(path, headers=admin_headers).json()[0]


@pytest.mark.parametrize(
    ("pagina", "path", "payload"),
    [
        ("veiculos", "/veiculos/{veiculo}", {"cor": "Prata"}),
        ("vendas", "/vendas/{venda}", {"observacoes": "ajustada"}),
        ("clientes", "/clientes/{cliente}", {"telefone": "11999999999"}),
        ("investidores", "/investidores/{investidor}", {"nome": "Ana Paula"}),
    ],
)
def test_api_factory_respeita_operacao_de_edicao_por_perfil(
    client: TestClient, pagina: str, path: str, payload: dict[str, object]
) -> None:
    ids = _seed(client, _headers(client, "admin"))
    url = path.format(**ids)
    _perfil_vendedor(
        f"{pagina} editor",
        [pagina],
        {pagina: {"campos_ocultos": [], "operacoes": ["editar"]}},
    )

    permitido = client.patch(url, json=payload, headers=_headers(client, "vendedor"))
    assert permitido.status_code == 200, permitido.text

    _perfil_vendedor(
        f"{pagina} leitor",
        [pagina],
        {pagina: {"campos_ocultos": [], "operacoes": []}},
    )
    bloqueado = client.patch(url, json=payload, headers=_headers(client, "vendedor"))
    assert bloqueado.status_code == 403
