"""UI HTMX: login por cookie e proteção das telas."""

import contextlib
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from xtreme_system.api.core import app
from xtreme_system.api.routes.ui import _validar_uploads
from xtreme_system.database.core import Base, get_session
from xtreme_system.investidor import core as investidor
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
                investidor_id=inv.id,
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


def test_upload_imagem_veiculo_salva_url_estatica_acessivel(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    resp = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto.jpg", b"conteudo-da-foto", "image/jpeg")},
    )
    assert resp.status_code == 200

    match = re.search(r'src="([^"]+/foto[^"]*)"', resp.text)
    if match is None:
        match = re.search(r'src="([^"]+\.jpg)"', resp.text)
    assert match is not None
    url = match.group(1)

    try:
        arquivo = client.get(url)
        assert arquivo.status_code == 200
        assert arquivo.content == b"conteudo-da-foto"
    finally:
        with contextlib.suppress(FileNotFoundError):
            Path("bases/xtreme_system/api").joinpath(url.lstrip("/")).unlink()


def test_modal_imagens_ignora_url_estatica_sem_arquivo(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    upload = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto.jpg", b"conteudo-da-foto", "image/jpeg")},
    )
    match = re.search(r'src="([^"]+\.jpg)"', upload.text)
    assert match is not None
    url = match.group(1)
    Path("bases/xtreme_system/api").joinpath(url.lstrip("/")).unlink()

    resp = client.get(f"/ui/veiculos/{veiculo_id}/imagens")

    assert resp.status_code == 200
    assert url not in resp.text


def test_ui_cria_veiculo_com_debitos_documento_e_modal_vendedor(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)

    resp = client.post(
        "/ui/veiculos",
        data={
            "tipo": "carro",
            "tipo_entrada": "compra",
            "placa": "DOC1A23",
            "modelo": "Civic",
            "cor": "Branco",
            "ano": "2023",
            "km": "5000",
            "preco": "95000.00",
            "debitos": "1234.56",
            "investidor_id": "1",
            "cli_nome": "Cliente Vendedor",
            "cli_documento": "11122233344",
            "cli_tipo": "pessoa_fisica",
            "cli_telefone": "11999999999",
            "cli_email": "vendedor@example.com",
        },
        files={
            "documentos_cliente": (
                "documento.pdf",
                b"conteudo-do-documento",
                "application/pdf",
            )
        },
    )
    assert resp.status_code == 200
    assert "Civic" in resp.text
    assert "R$ 1.234,56" in resp.text

    veiculos = client.get("/veiculos", headers=headers).json()
    veiculo_id = next(item["id"] for item in veiculos if item["placa"] == "DOC1A23")

    modal = client.get(f"/ui/veiculos/{veiculo_id}/cliente-vendedor")
    assert modal.status_code == 200
    assert "Cliente Vendedor" in modal.text
    assert "11122233344" in modal.text
    assert "R$ 1.234,56" in modal.text
    assert "Documento 1" in modal.text

    editar = client.get(f"/ui/veiculos/{veiculo_id}/editar")
    assert editar.status_code == 200
    assert "Revisão" in editar.text
    assert "Débito" in editar.text
    assert "Procurador" in editar.text
    assert "1234.56" in editar.text

    salvo = client.post(
        f"/ui/veiculos/{veiculo_id}",
        data={
            "tipo": "carro",
            "tipo_entrada": "compra",
            "placa": "DOC1A23",
            "modelo": "Civic",
            "cor": "Branco",
            "ano": "2023",
            "km": "5000",
            "preco": "95000.00",
            "revisao": "true",
            "debitos": "2000.00",
            "procuracao": "Fulano",
            "investidor_id": "1",
        },
    )
    assert salvo.status_code == 200
    assert "Fulano" in salvo.text
    assert "✓" in salvo.text
    assert "R$ 2.000,00" in salvo.text

    match = re.search(r'href="([^"]+\.pdf)"', modal.text)
    assert match is not None
    url = match.group(1)
    try:
        arquivo = client.get(url)
        assert arquivo.status_code == 200
        assert arquivo.content == b"conteudo-do-documento"
    finally:
        with contextlib.suppress(FileNotFoundError):
            Path("bases/xtreme_system/api").joinpath(url.lstrip("/")).unlink()


def test_ui_clientes_crud_basico(client: TestClient) -> None:
    _login_admin(client)

    pagina = client.get("/ui/clientes")
    assert pagina.status_code == 200
    assert 'id="linhas"' in pagina.text

    criado = client.post(
        "/ui/clientes",
        data={
            "nome": "Maria Lima",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
            "ativo": "true",
        },
    )
    assert criado.status_code == 200
    assert "Maria Lima" in criado.text

    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    clientes = client.get("/clientes", headers=headers).json()
    cliente_id = next(
        item["id"] for item in clientes if item["documento"] == "12345678901"
    )

    editado = client.post(
        f"/ui/clientes/{cliente_id}",
        data={
            "nome": "Maria Lima",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
            "cidade": "São Paulo",
            "ativo": "false",
        },
    )
    assert editado.status_code == 200
    assert "São Paulo" in editado.text

    excluido = client.post(f"/ui/clientes/{cliente_id}/excluir")
    assert excluido.status_code == 200
    assert "Maria Lima" not in excluido.text


def test_ui_clientes_documentos_modal_crud(client: TestClient) -> None:
    _login_admin(client)

    criado = client.post(
        "/ui/clientes",
        data={
            "nome": "João Documento",
            "documento": "98765432109",
            "tipo": "pessoa_fisica",
            "ativo": "true",
        },
    )
    assert criado.status_code == 200

    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    clientes = client.get("/clientes", headers=headers).json()
    cliente_id = next(
        item["id"] for item in clientes if item["documento"] == "98765432109"
    )

    modal = client.get(f"/ui/clientes/{cliente_id}/documentos")
    assert modal.status_code == 200
    assert f'hx-post="/ui/clientes/{cliente_id}/documentos"' in modal.text
    assert 'type="file"' in modal.text
    assert "Enviar documentos" in modal.text

    upload = client.post(
        f"/ui/clientes/{cliente_id}/documentos",
        files=[("documentos", ("comprovante.pdf", b"conteudo-doc", "application/pdf"))],
    )
    assert upload.status_code == 200
    assert "João Documento" in upload.text
    assert "/documentos/" in upload.text

    match = re.search(
        r'hx-post="/ui/clientes/\d+/documentos/(?P<doc_id>\d+)/excluir"',
        upload.text,
    )
    assert match is not None
    doc_id = match.group("doc_id")

    arquivo = re.search(
        r"(?P<url>/static/uploads/clientes/\d+/documentos/[a-f0-9]+\.pdf)",
        upload.text,
    )
    assert arquivo is not None
    try:
        caminho = arquivo.group("url")
        salvo = client.get(caminho)
        assert salvo.status_code == 200
        assert salvo.content == b"conteudo-doc"
    finally:
        with contextlib.suppress(FileNotFoundError):
            Path("bases/xtreme_system/api").joinpath(caminho.lstrip("/")).unlink()

    excluido = client.post(f"/ui/clientes/{cliente_id}/documentos/{doc_id}/excluir")
    assert excluido.status_code == 200
    assert "Nenhum documento" in excluido.text


def test_ui_investidores_crud_basico(client: TestClient) -> None:
    _login_admin(client)

    criado = client.post("/ui/investidores", data={"nome": "Nova Investidora"})
    assert criado.status_code == 200
    assert "Nova Investidora" in criado.text
    assert "cell-num" in criado.text
    assert "R$ 0,00" in criado.text


def test_ui_vendas_crud_basico(client: TestClient) -> None:
    _login_admin(client)

    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cliente_resp = client.post(
        "/clientes",
        json={
            "nome": "Carlos Lima",
            "documento": "98765432100",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert cliente_resp.status_code == 201
    cliente_id = cliente_resp.json()["id"]

    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    pagina = client.get("/ui/vendas")
    assert pagina.status_code == 200
    assert 'id="linhas"' in pagina.text

    criado = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "valor_entrada": "10000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "pendente",
            "observacoes": "aguardando aprovação",
        },
    )
    assert criado.status_code == 200
    assert "Carlos Lima" in criado.text
    assert "HB20" not in criado.text

    venda_id = client.get("/vendas", headers=headers).json()[0]["id"]

    editado = client.post(
        f"/ui/vendas/{venda_id}",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "valor_entrada": "15000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "aprovado",
            "observacoes": "aprovada",
        },
    )
    assert editado.status_code == 200
    assert "Aprovado" in editado.text

    excluido = client.post(f"/ui/vendas/{venda_id}/excluir")
    assert excluido.status_code == 200
    assert "Carlos Lima" not in excluido.text

    csv_resp = client.get("/ui/vendas/exportar")
    assert csv_resp.status_code == 200
    assert (
        csv_resp.headers["content-disposition"] == 'attachment; filename="vendas.csv"'
    )
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Carlos Lima" not in csv_resp.text


def test_ui_exportacao_de_dados_downloada_csv(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})

    for path, name, expected in [
        ("/ui/veiculos/exportar", "veiculos.csv", "Onix"),
        ("/ui/investidores/exportar", "investidores.csv", "Investidor A"),
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
    # cria um vendedor pela UI
    client.post(
        "/ui/usuarios",
        data={"username": "vendedor_ui", "senha": "abc", "papel": "vendedor"},
    )
    pagina = client.get("/ui/usuarios")
    assert "vendedor_ui" in pagina.text

    # usa a API JSON para obter o ID (mesmo client, mesma sessão)
    headers = {"Authorization": "Bearer dummy"}
    # vamos criar token pra acessar a API
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    vendedor_id = next(u["id"] for u in usuarios if u["username"] == "vendedor_ui")

    resp = client.post(f"/ui/usuarios/{vendedor_id}/excluir")
    assert resp.status_code == 200
    assert "vendedor_ui" not in resp.text


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
    # cria vendedor pela UI
    client.post(
        "/ui/usuarios",
        data={"username": "ui_vendedor", "senha": "abc", "papel": "vendedor"},
    )
    # obtém id do vendedor via API JSON
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    vendedor_id = next(u["id"] for u in usuarios if u["username"] == "ui_vendedor")

    # pega o form de senha
    resp = client.get(f"/ui/usuarios/{vendedor_id}/senha")
    assert resp.status_code == 200
    assert "nova_senha" in resp.text

    # envia nova senha
    resp = client.post(
        f"/ui/usuarios/{vendedor_id}/senha",
        data={"nova_senha": "ui_nova"},
    )
    assert resp.status_code == 200

    # login com nova senha
    resp = client.post(
        "/ui/login",
        data={"username": "ui_vendedor", "password": "ui_nova"},
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
        },
        headers=headers,
    )

    _login_admin(client)
    pagina = client.get(f"/ui/investidores/{inv['id']}/lancamentos")
    assert pagina.status_code == 200
    assert "HB20" in pagina.text
    assert "20.000,00" in pagina.text


def test_ui_nao_exclui_investidor_com_lancamentos(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Carlos"}, headers=headers).json()
    client.post(
        "/lancamentos-caixa",
        json={
            "investidor_id": inv["id"],
            "tipo": "aporte",
            "valor": "1000.00",
            "descricao": "Aporte inicial",
        },
        headers=headers,
    )

    resp = client.post(f"/ui/investidores/{inv['id']}/excluir")

    assert resp.status_code == 409
    assert "Não é possível excluir investidor com lançamentos." in resp.text
    assert "Carlos" in resp.text


def test_lancamento_de_veiculo_nao_pode_ser_editado_ou_excluido_via_api(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Dora"}, headers=headers).json()
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


def test_ui_dashboard_mostra_kpis(client: TestClient) -> None:
    """Dashboard admin mostra KPIs de vendas e estoque."""
    _login_admin(client)

    # sem vendas, deve retornar 200 com dados zerados
    resp = client.get("/ui/dashboard")
    assert resp.status_code == 200
    assert "Dashboard" in resp.text
    assert "Vendas este mês" in resp.text
    assert "Taxa de conversão" in resp.text

    # adiciona uma venda para ter dados não-zero
    resp_client = client.post("/login", data={"username": "admin", "password": "senha"})
    token = resp_client.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # criar cliente para venda
    cli = client.post(
        "/clientes",
        json={
            "nome": "João Silva",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    ).json()

    # criar veículo para venda
    vei = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Civic",
            "cor": "Branco",
            "ano": 2023,
            "placa": "XYZ9999",
            "km": 5000,
            "preco": "95000.00",
            "investidor_id": 1,  # fixture já cria Investidor A com id=1
        },
        headers=headers,
    ).json()

    # criar venda
    client.post(
        "/vendas",
        json={
            "cliente_id": cli["id"],
            "veiculo_id": vei["id"],
            "data_venda": "2026-07-10",
            "valor_venda": "95000.00",
            "forma_pagamento": "financiamento",
            "parcelas": 60,
        },
        headers=headers,
    )

    # dashboard agora mostra a venda
    resp = client.get("/ui/dashboard")
    assert resp.status_code == 200
    assert "95000" in resp.text or "95.000" in resp.text  # valor venda aparece
    assert "1" in resp.text  # contagem de vendas > 0


# ---- Validação de uploads ----


class _FakeFile:
    """Minimal file-like stub with seek/tell for size fallback in tests."""

    def __init__(self, size: int):
        self._size = size
        self._pos = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        self._pos = self._size + offset if whence == 2 else offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, _n: int = -1) -> bytes:
        return b""


class _FakeUpload:
    """Minimal UploadFile-like stub for unit tests (no network, no spooled file)."""

    def __init__(self, filename: str, content_type: str | None, size: int | None):
        self.filename = filename
        self.content_type = content_type
        self._size = size
        self.file = _FakeFile(size or 0)

    @property
    def size(self) -> int | None:
        return self._size


def test_validar_uploads_extensao_invalida() -> None:
    arq = _FakeUpload("malicioso.gif", "image/gif", 100)
    msg = _validar_uploads([arq])  # type: ignore[list-item]
    assert msg is not None
    assert "Tipo não permitido" in msg
    assert ".gif" in msg


def test_validar_uploads_extensao_valida_passa() -> None:
    for nome, ct in [
        ("foto.jpg", "image/jpeg"),
        ("foto.JPEG", "image/jpeg"),
        ("diagrama.png", "image/png"),
        ("arte.webp", "image/webp"),
        ("contrato.pdf", "application/pdf"),
    ]:
        arq = _FakeUpload(nome, ct, 1000)
        assert _validar_uploads([arq]) is None, f"{nome} deveria passar"  # type: ignore[list-item]


def test_validar_uploads_content_type_divergente() -> None:
    arq = _FakeUpload("foto.jpg", "application/pdf", 1000)
    msg = _validar_uploads([arq])  # type: ignore[list-item]
    assert msg is not None
    assert "Conteúdo não corresponde" in msg


def test_validar_uploads_content_type_ausente_passa() -> None:
    arq = _FakeUpload("foto.jpg", None, 1000)
    assert _validar_uploads([arq]) is None  # type: ignore[list-item]


def test_validar_uploads_arquivo_maior_que_5mb() -> None:
    arq = _FakeUpload("grande.jpg", "image/jpeg", 5 * 1024 * 1024 + 1)
    msg = _validar_uploads([arq])  # type: ignore[list-item]
    assert msg is not None
    assert "excede 5 MB" in msg


def test_validar_uploads_lote_rejeitado_se_um_falha() -> None:
    bons = _FakeUpload("ok.jpg", "image/jpeg", 1000)
    mau = _FakeUpload("mau.exe", "application/octet-stream", 1000)
    msg = _validar_uploads([bons, mau])  # type: ignore[list-item]
    assert msg is not None
    assert "Tipo não permitido" in msg


def test_validar_uploads_sem_filename_ignorado() -> None:
    arq = _FakeUpload("", None, None)
    assert _validar_uploads([arq]) is None  # type: ignore[list-item]


def test_post_com_content_length_maior_que_20mb_retorna_413(
    client: TestClient,
) -> None:
    _login_admin(client)
    resp = client.post(
        "/ui/veiculos/1/imagens",
        content=b"",
        headers={"Content-Length": str(21 * 1024 * 1024)},
    )
    assert resp.status_code == 413


def test_upload_imagem_veiculo_extensao_invalida_rejeitada(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    resp = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("malicioso.gif", b"dados", "image/gif")},
    )
    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    assert ".gif" in resp.text
