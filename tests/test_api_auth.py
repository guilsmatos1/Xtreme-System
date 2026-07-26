"""API auth: login, proteção por autenticação e por papel."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request

from xtreme_system.api import deps
from xtreme_system.api.core import app
from xtreme_system.auth import core as auth
from xtreme_system.database.core import get_session
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario


@pytest.fixture
def unique_plate() -> str:
    """Generate unique license plates for parallel test execution."""
    return f"ATH{uuid.uuid4().int % 10000:04d}"


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


def test_login_senha_errada(client: TestClient) -> None:
    resp = client.post("/login", data={"username": "admin", "password": "x"})
    assert resp.status_code == 401


def test_get_sem_token(client: TestClient) -> None:
    assert client.get("/investidores").status_code == 401


def test_get_current_user_binda_sessao_com_usuario_id(db_session: Session) -> None:
    admin = usuario.Usuario(
        username="admin",
        senha_hash=auth.hash_password("senha"),
        papel=usuario.Papel.admin,
    )
    db_session.add(admin)
    db_session.flush()

    token = auth.create_access_token(admin.username)

    user = deps.get_current_user(token, db_session)

    assert user.id == admin.id
    assert db_session.info["usuario_id"] == admin.id


def test_admin_authorization_uses_database_role_not_token_claim(
    db_session: Session,
) -> None:
    admin = usuario.Usuario(
        username="admin",
        senha_hash=auth.hash_password("senha"),
        papel=usuario.Papel.admin,
    )
    db_session.add(admin)
    db_session.flush()

    token = auth.create_access_token(admin.username)
    admin.papel = usuario.Papel.funcionario
    db_session.flush()

    user = deps.get_current_user(token, db_session)

    with pytest.raises(HTTPException) as exc:
        deps.require_admin(user)
    assert exc.value.status_code == 403


def test_get_ui_user_binda_sessao_com_usuario_id(db_session: Session) -> None:
    admin = usuario.Usuario(
        username="admin",
        senha_hash=auth.hash_password("senha"),
        papel=usuario.Papel.admin,
    )
    db_session.add(admin)
    db_session.flush()

    token = auth.create_access_token(admin.username)
    request = Request(
        {
            "type": "http",
            "path": "/ui/investidores",
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
            "headers": [],
        }
    )

    user = deps.get_ui_user(request, db_session, access_token=token)

    assert user.id == admin.id
    assert db_session.info["usuario_id"] == admin.id


def test_vendedor_sem_perfil_nao_le_json_de_pagina_restrita(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    assert client.get("/investidores", headers=headers).status_code == 403


def test_vendedor_com_perfil_pode_ler_json_da_pagina(client: TestClient) -> None:
    session = next(app.dependency_overrides[get_session]())
    p = perfil.create(
        session,
        perfil.PerfilCreate(nome="Investidores", paginas=["investidores"]),
    )
    vendedor = usuario.get_by_username(session, "vendedor")
    assert vendedor is not None
    vendedor.perfil_id = p.id
    session.flush()

    headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    assert client.get("/investidores", headers=headers).status_code == 200


def test_vendedor_nao_escreve(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'vendedor')}"}
    resp = client.post("/investidores", json={"nome": "Ana"}, headers=headers)
    assert resp.status_code == 403


def test_admin_escreve(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    resp = client.post("/investidores", json={"nome": "Ana"}, headers=headers)
    assert resp.status_code == 201


def test_json_crud_lista_paginal_e_rejeita_parametros_invalidos(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    for nome in ("Ana", "Bia", "Caio"):
        resp = client.post("/investidores", json={"nome": nome}, headers=headers)
        assert resp.status_code == 201

    resp = client.get(
        "/investidores", params={"limit": 1, "offset": 1}, headers=headers
    )

    assert resp.status_code == 200
    assert [item["nome"] for item in resp.json()] == ["Bia"]
    assert (
        client.get("/investidores", params={"limit": 201}, headers=headers).status_code
        == 422
    )
    assert (
        client.get("/investidores", params={"limit": 0}, headers=headers).status_code
        == 422
    )
    assert (
        client.get("/investidores", params={"offset": -1}, headers=headers).status_code
        == 422
    )


def test_json_usuarios_lista_paginal(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    client.post(
        "/usuarios",
        json={"username": "admin2", "senha": "senha", "papel": "admin"},
        headers=headers,
    )

    resp = client.get("/usuarios", params={"limit": 1, "offset": 1}, headers=headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_remover_investidor_com_veiculo_vinculado_retorna_409(
    client: TestClient, unique_plate: str
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    inv_id = client.post("/investidores", json={"nome": "Ana"}, headers=headers).json()[
        "id"
    ]
    client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Gol",
            "cor": "Branco",
            "ano": 2018,
            "placa": unique_plate,
            "km": 70000,
            "preco": "32000.00",
            "investidor_id": inv_id,
        },
        headers=headers,
    )

    resp = client.delete(f"/investidores/{inv_id}", headers=headers)
    assert resp.status_code == 409


def test_admin_nao_pode_se_autoexcluir(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    admin_id = next(u["id"] for u in usuarios if u["username"] == "admin")
    resp = client.delete(f"/usuarios/{admin_id}", headers=headers)
    assert resp.status_code == 400


def test_admin_pode_excluir_outro_admin(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    # cria outro admin
    outro = client.post(
        "/usuarios",
        json={"username": "admin2", "senha": "senha", "papel": "admin"},
        headers=headers,
    )
    assert outro.status_code == 201
    outro_id = outro.json()["id"]

    resp = client.delete(f"/usuarios/{outro_id}", headers=headers)
    assert resp.status_code == 204

    # confere que foi removido
    usuarios = client.get("/usuarios", headers=headers).json()
    assert not any(u["id"] == outro_id for u in usuarios)


def test_admin_pode_trocar_senha_de_outro(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    # cria um vendedor
    vendedor = client.post(
        "/usuarios",
        json={"username": "vendedor2", "senha": "abc", "papel": "funcionario"},
        headers=headers,
    )
    assert vendedor.status_code == 201
    vendedor_id = vendedor.json()["id"]

    resp = client.post(
        f"/usuarios/{vendedor_id}/senha",
        data={"nova_senha": "nova123"},
        headers=headers,
    )
    assert resp.status_code == 204

    # login com a nova senha deve funcionar
    resp2 = client.post("/login", data={"username": "vendedor2", "password": "nova123"})
    assert resp2.status_code == 200


def test_api_usuario_management_atribui_admin_na_auditoria(
    client: TestClient,
) -> None:
    """Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin
    como autor nas linhas de auditoria (não None)."""
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    admin_id = next(u["id"] for u in usuarios if u["username"] == "admin")

    # CREATE
    novo = client.post(
        "/usuarios",
        json={"username": "alvo", "senha": "s", "papel": "funcionario"},
        headers=headers,
    )
    assert novo.status_code == 201
    alvo_id = novo.json()["id"]

    # UPDATE (trocar senha)
    assert (
        client.post(
            f"/usuarios/{alvo_id}/senha",
            data={"nova_senha": "nova"},
            headers=headers,
        ).status_code
        == 204
    )

    # DELETE
    assert client.delete(f"/usuarios/{alvo_id}", headers=headers).status_code == 204

    rows = client.get(
        "/auditoria", params={"tabela": "usuario"}, headers=headers
    ).json()
    por_acao: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r["registro_id"] == alvo_id:
            por_acao.setdefault(r["tipo_acao"], []).append(r)

    assert por_acao["CREATE"]
    assert all(r["usuario_id"] == admin_id for r in por_acao["CREATE"])
    assert por_acao["UPDATE"]
    assert all(r["usuario_id"] == admin_id for r in por_acao["UPDATE"])
    assert por_acao["DELETE"]
    assert all(r["usuario_id"] == admin_id for r in por_acao["DELETE"])


def test_auditoria_rejeita_limit_offset_invalidos(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}

    assert (
        client.get("/auditoria", params={"limit": 201}, headers=headers).status_code
        == 422
    )
    assert (
        client.get("/auditoria", params={"limit": 0}, headers=headers).status_code
        == 422
    )
    assert (
        client.get("/auditoria", params={"offset": -1}, headers=headers).status_code
        == 422
    )


def test_placa_duplicada_retorna_400(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    inv_id = client.post("/investidores", json={"nome": "Ana"}, headers=headers).json()[
        "id"
    ]
    veiculo_data = {
        "tipo": "carro",
        "modelo": "Fusca",
        "cor": "Azul",
        "ano": 1975,
        "placa": "XYZ1234",
        "km": 100000,
        "preco": "15000.00",
        "investidor_id": inv_id,
    }
    r1 = client.post("/veiculos", json=veiculo_data, headers=headers)
    assert r1.status_code == 201

    r2 = client.post("/veiculos", json=veiculo_data, headers=headers)
    assert r2.status_code == 400
    assert "placa" in r2.json()["detail"].lower()
