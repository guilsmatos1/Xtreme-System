"""API auth: login, proteção por autenticação e por papel."""

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
                username="leitor", senha="senha", papel=usuario.Papel.leitor
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


def test_login_senha_errada(client: TestClient) -> None:
    resp = client.post("/login", data={"username": "admin", "password": "x"})
    assert resp.status_code == 401


def test_get_sem_token(client: TestClient) -> None:
    assert client.get("/investidores").status_code == 401


def test_leitor_pode_ler(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'leitor')}"}
    assert client.get("/investidores", headers=headers).status_code == 200


def test_leitor_nao_escreve(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'leitor')}"}
    resp = client.post("/investidores", json={"nome": "Ana"}, headers=headers)
    assert resp.status_code == 403


def test_admin_escreve(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    resp = client.post("/investidores", json={"nome": "Ana"}, headers=headers)
    assert resp.status_code == 201


def test_remover_investidor_com_veiculo_vinculado_retorna_409(
    client: TestClient,
) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    inv_id = client.post("/investidores", json={"nome": "Ana"}, headers=headers).json()[
        "id"
    ]
    meio_id = client.post(
        "/meios-captacao", json={"nome": "Instagram"}, headers=headers
    ).json()["id"]
    client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Gol",
            "cor": "Branco",
            "ano": 2018,
            "placa": "AAA1B22",
            "km": 70000,
            "preco": "32000.00",
            "investidor_id": inv_id,
            "meio_captacao_id": meio_id,
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
    # cria um leitor
    leitor = client.post(
        "/usuarios",
        json={"username": "leitor2", "senha": "abc", "papel": "leitor"},
        headers=headers,
    )
    assert leitor.status_code == 201
    leitor_id = leitor.json()["id"]

    resp = client.post(
        f"/usuarios/{leitor_id}/senha",
        data={"nova_senha": "nova123"},
        headers=headers,
    )
    assert resp.status_code == 204

    # login com a nova senha deve funcionar
    resp2 = client.post("/login", data={"username": "leitor2", "password": "nova123"})
    assert resp2.status_code == 200


def test_placa_duplicada_retorna_400(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    inv_id = client.post("/investidores", json={"nome": "Ana"}, headers=headers).json()[
        "id"
    ]
    meio_id = client.post(
        "/meios-captacao", json={"nome": "Site"}, headers=headers
    ).json()["id"]

    veiculo_data = {
        "tipo": "carro",
        "modelo": "Fusca",
        "cor": "Azul",
        "ano": 1975,
        "placa": "XYZ1234",
        "km": 100000,
        "preco": "15000.00",
        "investidor_id": inv_id,
        "meio_captacao_id": meio_id,
    }
    r1 = client.post("/veiculos", json=veiculo_data, headers=headers)
    assert r1.status_code == 201

    r2 = client.post("/veiculos", json=veiculo_data, headers=headers)
    assert r2.status_code == 400
    assert "placa" in r2.json()["detail"].lower()
