"""UI HTMX: login por cookie e proteção das telas."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from xtreme_system.api.core import app
from xtreme_system.database.core import Base, get_session
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


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
        inv = investidor.create(
            session, investidor.InvestidorCreate(nome="Investidor A")
        )
        meio = meio_captacao.create(
            session, meio_captacao.MeioCaptacaoCreate(nome="Site")
        )
        veiculo.create(
            session,
            veiculo.VeiculoCreate(
                tipo=veiculo.TipoVeiculo.carro,
                modelo="Onix",
                cor="Prata",
                ano=2024,
                placa="ABC1234",
                km=12000,
                preco=85000,
                status=veiculo.StatusVeiculo.disponivel,
                investidor_id=inv.id,
                meio_captacao_id=meio.id,
            ),
        )

        def override() -> Iterator[Session]:
            yield session

        app.dependency_overrides[get_session] = override
        yield TestClient(app)
        app.dependency_overrides.clear()


def test_ui_veiculos_sem_cookie_redireciona_login() -> None:
    with TestClient(app) as client:
        resp = client.get("/ui/veiculos", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/ui/login"


def test_ui_login_seta_cookie_e_lista_veiculos(client: TestClient) -> None:
    resp = client.post(
        "/ui/login",
        data={"username": "admin", "password": "senha"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "access_token" in resp.cookies

    pagina = client.get("/ui/veiculos")
    assert pagina.status_code == 200
    assert 'id="linhas"' in pagina.text
    assert "Exportar dados" in pagina.text


def test_ui_exportacao_de_dados_downloada_csv(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})

    for path, name, expected in [
        ("/ui/veiculos/exportar", "veiculos.csv", "Onix"),
        ("/ui/investidores/exportar", "investidores.csv", "Investidor A"),
        ("/ui/meios-captacao/exportar", "meios-captacao.csv", "Site"),
        ("/ui/usuarios/exportar", "usuarios.csv", "admin"),
    ]:
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.headers["content-disposition"] == f'attachment; filename="{name}"'
        assert "text/csv" in resp.headers["content-type"]
        assert expected in resp.text


def _login_admin(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})


def test_ui_admin_exclui_outro_usuario(client: TestClient) -> None:
    """Admin pode excluir outro usuário pela UI."""
    _login_admin(client)
    # cria um leitor pela UI
    client.post(
        "/ui/usuarios",
        data={"username": "leitor_ui", "senha": "abc", "papel": "leitor"},
    )
    pagina = client.get("/ui/usuarios")
    assert "leitor_ui" in pagina.text

    # usa a API JSON para obter o ID (mesmo client, mesma sessão)
    headers = {"Authorization": "Bearer dummy"}
    # vamos criar token pra acessar a API
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    leitor_id = next(u["id"] for u in usuarios if u["username"] == "leitor_ui")

    resp = client.post(f"/ui/usuarios/{leitor_id}/excluir")
    assert resp.status_code == 200
    assert "leitor_ui" not in resp.text


def test_ui_admin_nao_pode_se_autoexcluir(client: TestClient) -> None:
    """Admin não pode excluir a si mesmo pela UI."""
    _login_admin(client)
    # obtém o id do admin
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    admin_id = next(u["id"] for u in usuarios if u["username"] == "admin")

    resp = client.post(f"/ui/usuarios/{admin_id}/excluir")
    assert resp.status_code == 400
    assert "não pode excluir a si mesmo" in resp.text.lower()


def test_ui_admin_troca_senha_de_outro(client: TestClient) -> None:
    """Admin pode trocar a senha de outro usuário pela UI."""
    _login_admin(client)
    # cria leitor pela UI
    client.post(
        "/ui/usuarios",
        data={"username": "ui_leitor", "senha": "abc", "papel": "leitor"},
    )
    # obtém id do leitor via API JSON
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    leitor_id = next(u["id"] for u in usuarios if u["username"] == "ui_leitor")

    # pega o form de senha
    resp = client.get(f"/ui/usuarios/{leitor_id}/senha")
    assert resp.status_code == 200
    assert "nova_senha" in resp.text

    # envia nova senha
    resp = client.post(
        f"/ui/usuarios/{leitor_id}/senha",
        data={"nova_senha": "ui_nova"},
    )
    assert resp.status_code == 200

    # login com nova senha
    resp = client.post(
        "/ui/login",
        data={"username": "ui_leitor", "password": "ui_nova"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def _admin_headers(client: TestClient) -> dict[str, str]:
    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_veiculo_criado_via_api_gera_lancamento_visivel_no_caixa(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Carla"}, headers=headers).json()
    meio = client.post(
        "/meios-captacao", json={"nome": "Indicação"}, headers=headers
    ).json()
    client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "HB20",
            "cor": "Preto",
            "ano": 2022,
            "placa": "ZZZ9Z99",
            "km": 1000,
            "preco": "20000.00",
            "investidor_id": inv["id"],
            "meio_captacao_id": meio["id"],
        },
        headers=headers,
    )

    _login_admin(client)
    pagina = client.get(f"/ui/caixa/{inv['id']}")
    assert pagina.status_code == 200
    assert "HB20" in pagina.text
    assert "20.000,00" in pagina.text


def test_lancamento_de_veiculo_nao_pode_ser_editado_ou_excluido_via_api(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Dora"}, headers=headers).json()
    meio = client.post(
        "/meios-captacao", json={"nome": "Rádio"}, headers=headers
    ).json()
    v = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Kwid",
            "cor": "Branco",
            "ano": 2023,
            "placa": "YYY8Y88",
            "km": 500,
            "preco": "18000.00",
            "investidor_id": inv["id"],
            "meio_captacao_id": meio["id"],
        },
        headers=headers,
    ).json()
    lancamentos = client.get("/lancamentos-caixa", headers=headers).json()
    lanc = next(item for item in lancamentos if item["veiculo_id"] == v["id"])

    resp = client.patch(
        f"/lancamentos-caixa/{lanc['id']}", json={"valor": "1.00"}, headers=headers
    )
    assert resp.status_code == 400

    resp = client.delete(f"/lancamentos-caixa/{lanc['id']}", headers=headers)
    assert resp.status_code == 400


def test_editar_preco_ou_investidor_do_veiculo_via_api_sincroniza_caixa(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Eva"}, headers=headers).json()
    outro = client.post("/investidores", json={"nome": "Fabio"}, headers=headers).json()
    meio = client.post("/meios-captacao", json={"nome": "TV"}, headers=headers).json()
    v = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Argo",
            "cor": "Cinza",
            "ano": 2021,
            "placa": "XXX7X77",
            "km": 300,
            "preco": "15000.00",
            "investidor_id": inv["id"],
            "meio_captacao_id": meio["id"],
        },
        headers=headers,
    ).json()

    resp = client.patch(
        f"/veiculos/{v['id']}",
        json={"preco": "17000.00", "investidor_id": outro["id"]},
        headers=headers,
    )
    assert resp.status_code == 200

    lancamentos = client.get("/lancamentos-caixa", headers=headers).json()
    lanc = next(item for item in lancamentos if item["veiculo_id"] == v["id"])
    assert lanc["valor"] == "17000.00"
    assert lanc["investidor_id"] == outro["id"]
