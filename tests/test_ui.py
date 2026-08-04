"""UI HTMX: login por cookie e proteção das telas."""

import contextlib
import re
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.api.core import app
from xtreme_system.api.deps import NaoAutorizadoError, get_ui_user
from xtreme_system.api.routes.ui_routes import compras as compras_ui
from xtreme_system.api.routes.ui_routes import dashboard as dashboard_ui
from xtreme_system.api.routes.ui_routes import veiculos_imagens as veiculos_imagens_ui
from xtreme_system.api.routes.ui_routes.client_resolution import resolver_cliente
from xtreme_system.api.routes.ui_routes.upload_validation import validar_uploads
from xtreme_system.api.routes.ui_routes.uploads import salvar_arquivos
from xtreme_system.auditoria import core as auditoria
from xtreme_system.auth import core as auth
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.custo_veiculo import core as custo_veiculo
from xtreme_system.database.core import get_session, invoke_post_commit
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.imagem_comprovante_compra import core as imagem_comprovante_compra
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.imagem_veiculo import core as imagem_veiculo
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda


def _seed_investidor_e_veiculo(session: Session) -> None:
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Investidor A"))
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


def _request(path: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": []})


class _FakeSession:
    def __init__(self) -> None:
        self.info: dict[str, Any] = {}


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=_seed_investidor_e_veiculo,
    )


def test_ui_veiculos_sem_cookie_redireciona_login() -> None:
    with TestClient(app) as client:
        resp = client.get("/ui/veiculos", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/ui/login"


def test_ui_configura_htmx_para_trocar_fragmentos_de_erro(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/veiculos")

    assert resp.status_code == 200
    assert '<meta name="htmx-config"' in resp.text
    assert "responseHandling" in resp.text
    assert "[45].." in resp.text
    assert "error" in resp.text


def test_ui_http_exception_retorna_html_para_swap_htmx(client: TestClient) -> None:
    _login_admin(client)

    resp = client.get("/ui/veiculos/999/detalhes")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == "Veículo não encontrado"
    assert resp.text != '{"detail":"Veículo não encontrado"}'


def test_ui_login_seta_cookie_e_lista_veiculos(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    resp = client.post(
        "/ui/login",
        data={"username": "admin", "password": "senha"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "access_token" in resp.cookies
    assert "authentication_succeeded" in caplog.text
    assert "admin" in caplog.text

    pagina = client.get("/ui/veiculos")
    assert pagina.status_code == 200
    assert 'id="linhas"' in pagina.text
    assert "Exportar dados" in pagina.text
    assert "Valor disponível" not in pagina.text


def test_ui_logout_invalida_cookie_no_servidor(client: TestClient) -> None:
    _login_admin(client)
    cookie_antigo = client.cookies.get("access_token")

    logout = client.post("/ui/logout", follow_redirects=False)

    assert logout.status_code == 303
    assert logout.headers["location"] == "/ui/login"
    assert cookie_antigo is not None
    session = next(app.dependency_overrides[get_session]())
    admin = usuario.get_by_username(session, "admin")
    assert admin is not None
    assert admin.token_version == 1
    stale_client = TestClient(app)
    stale_client.cookies.set("access_token", cookie_antigo)
    try:
        assert stale_client.get("/ui/conta", follow_redirects=False).status_code == 303
    finally:
        stale_client.close()


def test_ui_logout_apaga_cookie_secure_com_os_mesmos_atributos(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        client_kwargs={"base_url": "https://testserver"},
    )
    _login_admin(client)

    logout = client.post("/ui/logout", follow_redirects=False)

    assert logout.status_code == 303
    set_cookie = logout.headers["set-cookie"]
    assert 'access_token=""' in set_cookie
    assert "Path=/" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" in set_cookie
    assert "HttpOnly" in set_cookie


def test_ui_veiculo_preserva_erro_de_validacao_por_campo(client: TestClient) -> None:
    _login_admin(client)

    resp = client.post("/ui/veiculos/1", data={"km": "-1"})

    assert resp.status_code == 400
    assert "Quilometragem: deve ser maior ou igual a zero." in resp.text
    assert "km: Input should" not in resp.text


def test_ui_veiculo_renderiza_erros_de_validacao_em_linhas_separadas(
    client: TestClient,
) -> None:
    _login_admin(client)

    resp = client.post(
        "/ui/veiculos/1",
        data={"km": "-1", "preco": "nao-e-um-numero"},
    )

    assert resp.status_code == 400
    assert "Quilometragem: deve ser maior ou igual a zero." in resp.text
    assert "Preço anunciado: informe um valor numérico válido." in resp.text
    assert (
        "Quilometragem: deve ser maior ou igual a zero.<br>"
        "Preço anunciado: informe um valor numérico válido."
    ) in resp.text


def test_ui_ordenacao_de_veiculos_usa_htmx(client: TestClient) -> None:
    _login_admin(client)

    pagina = client.get("/ui/veiculos")

    assert pagina.status_code == 200
    assert 'hx-get="/ui/veiculos?sort=modelo&amp;order=asc' in pagina.text
    assert 'hx-target="#linhas"' in pagina.text

    busca_ordenada = client.get("/ui/veiculos?sort=preco&order=desc&q=ABC")
    assert 'name="sort" value="preco"' in busca_ordenada.text
    assert 'name="order" value="desc"' in busca_ordenada.text

    ordenada = client.get(
        "/ui/veiculos?sort=modelo&order=asc",
        headers={"HX-Request": "true"},
    )

    assert ordenada.status_code == 200
    assert '<tbody id="linhas"' in ordenada.text
    assert "<html" not in ordenada.text


def test_ui_excluir_veiculo_preserva_busca_atual(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    criado = client.post(
        "/veiculos",
        json={
            "tipo": "moto",
            "modelo": "Fora da busca",
            "cor": "Preta",
            "ano": 2025,
            "placa": "XYZ1234",
            "km": 0,
            "preco": "15000.00",
            "investidor_id": investidor_id,
            "tipo_entrada": "consignacao",
        },
        headers=headers,
    )
    assert criado.status_code == 201
    onix_id = next(
        item["id"]
        for item in client.get("/veiculos", headers=headers).json()
        if item["modelo"] == "Onix"
    )

    resp = client.post(
        f"/ui/veiculos/{onix_id}/excluir",
        headers={
            "HX-Current-URL": (
                "http://testserver/ui/veiculos?q=Onix&sort=modelo&order=desc"
            )
        },
    )

    assert resp.status_code == 200
    assert "Nenhum veículo encontrado" in resp.text
    assert "Fora da busca" not in resp.text


def _seed_veiculos_com_e_sem_compra(session: Session) -> None:
    """Um veículo comprado (tem custo) e um consignado (não tem)."""
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Investidor C"))
    cliente_obj = cliente.create(
        session,
        cliente.ClienteCreate(
            nome="Vendedor Custo",
            documento="12312312312",
            tipo=cliente.TipoCliente.pessoa_fisica,
        ),
    )
    comprado = veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Comprado",
            cor="Prata",
            ano=2024,
            placa="CPR1234",
            km=1000,
            preco=90000,
            investidor_id=inv.id,
        ),
    )
    veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Consignado",
            cor="Preto",
            ano=2024,
            placa="CSG1234",
            km=2000,
            preco=70000,
            tipo_entrada=veiculo.TipoEntrada.consignacao,
            investidor_id=inv.id,
        ),
    )
    compra.create(
        session,
        compra.CompraCreate(
            cliente_id=cliente_obj.id,
            veiculo_id=comprado.id,
            data_compra="2026-07-09",
            valor_compra=75000,
        ),
    )


def test_ui_veiculos_lista_mostra_so_preco_anunciado(
    make_client: Callable[..., TestClient],
) -> None:
    """A tabela /ui/veiculos não tem coluna de custo — só o detalhe do veículo tem."""
    local_client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=_seed_veiculos_com_e_sem_compra,
    )
    _login_admin(local_client)

    pagina = local_client.get("/ui/veiculos")

    assert pagina.status_code == 200
    assert 'data-col-label="Preço Anunciado"' in pagina.text
    assert 'data-col-label="Preço de Custo"' not in pagina.text
    assert 'data-col="custo"' not in pagina.text
    assert '<td class="cell-num cell-strong" data-col="preco">R$ 90.000,00</td>' in (
        pagina.text
    )


def test_ui_veiculo_detalhe_mostra_preco_de_custo_da_compra(
    make_client: Callable[..., TestClient],
) -> None:
    local_client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=_seed_veiculos_com_e_sem_compra,
    )
    _login_admin(local_client)

    comprado = local_client.get("/ui/veiculos/1/detalhes")
    assert comprado.status_code == 200
    assert "Preço Anunciado" in comprado.text
    assert "R$ 90.000,00" in comprado.text
    # custo vem do valor da compra, não do preço anunciado
    assert "R$ 75.000,00" in comprado.text

    consignado = local_client.get("/ui/veiculos/2/detalhes")
    assert consignado.status_code == 200
    assert "Preço de Custo" in consignado.text


def test_ui_perfis_novo_exibe_campo_preco_de_custo_de_veiculos(
    client: TestClient,
) -> None:
    _login_admin(client)

    pagina = client.get("/ui/perfis/novo")

    assert pagina.status_code == 200
    assert 'name="oculto__veiculos__custo"' in pagina.text
    assert 'name="oculto__veiculos__preco"' in pagina.text
    assert "Preço Anunciado" in pagina.text


def test_ui_veiculos_kpis_contam_todo_o_estoque(
    make_client: Callable[..., TestClient],
) -> None:
    def seed(session: Session) -> None:
        inv = investidor.create(
            session, investidor.InvestidorCreate(nome="Investidor KPI")
        )
        for index in range(51):
            veiculo.create(
                session,
                veiculo.VeiculoCreate(
                    tipo=veiculo.TipoVeiculo.carro,
                    modelo=f"KPI {index}",
                    cor="Prata",
                    ano=2024,
                    placa=f"KPI{index:04d}",
                    km=12000,
                    preco=85000,
                    investidor_id=inv.id,
                ),
            )

    local_client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=seed,
    )
    _login_admin(local_client)

    pagina = local_client.get("/ui/veiculos")

    assert pagina.status_code == 200
    assert re.search(
        r"Total no estoque</div>\s*<div class=\"stat__value cell-num\">51</div>",
        pagina.text,
    )
    assert pagina.text.count('id="veiculo-') == 50
    assert "Mostrando 1\N{EN DASH}50" in pagina.text
    assert "Próxima" in pagina.text

    segunda_pagina = local_client.get("/ui/veiculos?limit=50&offset=50")

    assert segunda_pagina.status_code == 200
    assert segunda_pagina.text.count('id="veiculo-') == 1
    assert "Mostrando 51\N{EN DASH}51" in segunda_pagina.text
    assert "Anterior" in segunda_pagina.text


def test_ui_veiculos_lista_com_km_vazio(
    make_client: Callable[..., TestClient],
) -> None:
    def seed(session: Session) -> None:
        inv = investidor.create(
            session, investidor.InvestidorCreate(nome="Investidor KM Vazio")
        )
        veiculo.create(
            session,
            veiculo.VeiculoCreate(
                tipo=veiculo.TipoVeiculo.carro,
                modelo="Onix",
                cor="Prata",
                ano=2024,
                placa="KMM0000",
                km=None,
                preco=85000,
                investidor_id=inv.id,
            ),
        )

    local_client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=seed,
    )
    _login_admin(local_client)

    pagina = local_client.get("/ui/veiculos")

    assert pagina.status_code == 200
    assert 'data-col="km">-' in pagina.text


def test_ui_auditoria_filtrar_aceita_selects_vazios(client: TestClient) -> None:
    _login_admin(client)

    pagina = client.get("/ui/auditoria")
    assert pagina.status_code == 200
    assert "data-omit-empty-params" in pagina.text

    com_datas = client.get(
        "/ui/auditoria",
        params={
            "data_de": "2026-07-19",
            "data_ate": "2026-07-20",
            "usuario_id": "",
            "tabela": "",
            "tipo_acao": "",
        },
        headers={"HX-Request": "true"},
    )

    assert com_datas.status_code == 200
    assert 'id="auditoria-resultado"' in com_datas.text

    sem_datas = client.get(
        "/ui/auditoria",
        params={
            "data_de": "",
            "data_ate": "",
            "usuario_id": "",
            "tabela": "",
            "tipo_acao": "",
        },
        headers={"HX-Request": "true"},
    )

    assert sem_datas.status_code == 200
    assert 'id="auditoria-resultado"' in sem_datas.text


def test_ui_perfis_novo_exibe_campo_debitos_de_veiculos(client: TestClient) -> None:
    _login_admin(client)

    pagina = client.get("/ui/perfis/novo")

    assert pagina.status_code == 200
    assert "Veículos — Campos a ocultar" in pagina.text
    assert "Débitos" in pagina.text


def test_ui_perfis_novo_exibe_cadastro_de_clientes_compras_e_vendas(
    client: TestClient,
) -> None:
    _login_admin(client)

    pagina = client.get("/ui/perfis/novo")

    assert pagina.status_code == 200
    for modulo in ("Clientes", "Compras", "Vendas"):
        assert f"{modulo} — Operações permitidas" in pagina.text
    assert 'name="op__clientes__cadastrar"' in pagina.text
    assert 'name="op__compras__cadastrar"' in pagina.text
    assert 'name="op__vendas__cadastrar"' in pagina.text


def test_ui_perfis_salva_cadastro_de_compras_e_vendas(client: TestClient) -> None:
    _login_admin(client)

    resp = client.post(
        "/ui/perfis",
        data={
            "nome": "Operador",
            "paginas": ["compras", "vendas"],
            "op__compras__cadastrar": "on",
            "op__vendas__cadastrar": "on",
        },
    )

    assert resp.status_code == 200
    form = client.get("/ui/perfis/1/editar")
    assert form.status_code == 200
    assert re.search(r'name="op__compras__cadastrar"\s+checked', form.text)
    assert re.search(r'name="op__vendas__cadastrar"\s+checked', form.text)


def test_ui_perfis_htmx_sucesso_dispara_toast_e_fecha_modal(client: TestClient) -> None:
    _login_admin(client)

    resp = client.post(
        "/ui/perfis",
        headers={"HX-Request": "true"},
        data={"nome": "Operador", "paginas": ["compras"]},
    )

    assert resp.status_code == 200
    assert resp.headers["HX-Trigger"] == (
        '{"htmx:toast": {"message": "Altera\\u00e7\\u00f5es salvas com sucesso."}, '
        '"htmx:close-modal": {}}'
    )


def test_ui_perfil_editar_rejeita_erro_de_validacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    criado = client.post("/ui/perfis", data={"nome": "Perfil para validar"})
    assert criado.status_code == 200

    perfil_update = perfil.PerfilUpdate

    def invalid_update(**_: object) -> perfil.PerfilUpdate:
        return perfil_update.model_validate({"paginas": 123})

    monkeypatch.setattr(perfil, "PerfilUpdate", invalid_update)

    resp = client.post("/ui/perfis/1", data={"nome": "Perfil alterado"})

    assert resp.status_code == 400
    assert "paginas" in resp.text


def test_ui_perfil_criar_retorna_conflito_em_integrity_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    criar = perfil.create

    def falhar_apos_criar(
        session: Session,
        data: perfil.PerfilCreate,
        actor_id: int | None = None,
    ) -> perfil.Perfil:
        criar(session, data, actor_id)
        raise IntegrityError("INSERT", {}, RuntimeError("perfil duplicado"))

    monkeypatch.setattr(perfil, "create", falhar_apos_criar)

    resp = client.post("/ui/perfis", data={"nome": "Perfil duplicado"})

    assert resp.status_code == 409
    assert "Perfil já existe" in resp.text


def test_ui_perfil_atualizar_retorna_conflito_em_integrity_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    criado = client.post("/ui/perfis", data={"nome": "Perfil original"})
    assert criado.status_code == 200
    next(app.dependency_overrides[get_session]()).commit()
    atualizar = perfil.update

    def falhar_apos_atualizar(
        session: Session,
        obj: perfil.Perfil,
        data: perfil.PerfilUpdate,
        actor_id: int | None = None,
    ) -> perfil.Perfil:
        atualizar(session, obj, data, actor_id)
        raise IntegrityError("UPDATE", {}, RuntimeError("perfil duplicado"))

    monkeypatch.setattr(perfil, "update", falhar_apos_atualizar)

    resp = client.post("/ui/perfis/1", data={"nome": "Perfil duplicado"})

    assert resp.status_code == 409
    assert "Perfil já existe" in resp.text


def test_ui_perfil_excluir_retorna_conflito_em_integrity_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    criado = client.post("/ui/perfis", data={"nome": "Perfil vinculado"})
    assert criado.status_code == 200
    excluir = perfil.delete

    def falhar_apos_excluir(
        session: Session,
        obj: perfil.Perfil,
        actor_id: int | None = None,
    ) -> None:
        excluir(session, obj, actor_id)
        raise IntegrityError("DELETE", {}, RuntimeError("perfil vinculado"))

    monkeypatch.setattr(perfil, "delete", falhar_apos_excluir)

    resp = client.post("/ui/perfis/1/excluir")

    assert resp.status_code == 409
    assert "Perfil possui usuários vinculados" in resp.text


def test_upload_imagem_veiculo_salva_url_estatica_acessivel(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    resp = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto.jpg", b"\xff\xd8\xffconteudo-da-foto", "image/jpeg")},
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
        assert arquivo.content == b"\xff\xd8\xffconteudo-da-foto"
    finally:
        with contextlib.suppress(FileNotFoundError):
            Path("bases/xtreme_system/api").joinpath(url.lstrip("/")).unlink()


def test_modal_imagens_marca_arquivo_faltante_ao_abrir(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    upload = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto.jpg", b"\xff\xd8\xffconteudo-da-foto", "image/jpeg")},
    )
    match = re.search(r'src="([^"]+\.jpg)"', upload.text)
    assert match is not None
    url = match.group(1)
    Path("bases/xtreme_system/api").joinpath(url.lstrip("/")).unlink()

    resp = client.get(f"/ui/veiculos/{veiculo_id}/imagens")

    assert resp.status_code == 200
    assert "Indisponível" in resp.text
    assert Path(url).name in resp.text
    assert client.get(url).status_code == 404


def test_modal_imagens_veiculo_get_renderiza_acoes_com_imagem_existente(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    upload = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto.jpg", b"\xff\xd8\xffconteudo-da-foto", "image/jpeg")},
    )
    assert upload.status_code == 200

    resp = client.get(f"/ui/veiculos/{veiculo_id}/imagens")

    assert resp.status_code == 200
    assert 'hx-post="/ui/veiculos/' in resp.text
    assert 'name="imagens"' in resp.text


def test_ui_clientes_todos_lista_e_edita(  # noqa: PLR0915
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

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

    comprador_id = _criar_cliente(client, headers, "Ana Compradora", "12345678901")
    ambos_id = _criar_cliente(client, headers, "Caio Ambos", "12345678903")
    _criar_cliente(client, headers, "Dora Sem Vinculo", "12345678904")
    vendedor_resp = client.post(
        "/clientes",
        json={
            "nome": "Bia Vendedora",
            "documento": "12345678000102",
            "tipo": "pessoa_juridica",
        },
        headers=headers,
    )
    assert vendedor_resp.status_code == 201
    vendedor_id = int(vendedor_resp.json()["id"])

    venda_resp = client.post(
        "/vendas",
        json={
            "cliente_id": comprador_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "pix",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda_resp.status_code == 201
    compra_resp = client.post(
        "/compras",
        json={
            "cliente_id": vendedor_id,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-08",
            "valor_compra": "80000.00",
        },
        headers=headers,
    )
    assert compra_resp.status_code == 201
    assert (
        client.post(
            "/vendas",
            json={
                "cliente_id": ambos_id,
                "veiculo_id": veiculo2_id,
                "data_venda": "2026-07-10",
                "valor_venda": "86000.00",
                "forma_pagamento": "pix",
                "parcelas": 1,
                "status": "pendente",
            },
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/compras",
            json={
                "cliente_id": ambos_id,
                "veiculo_id": veiculo_id,
                "data_compra": "2026-07-07",
                "valor_compra": "79000.00",
            },
            headers=headers,
        ).status_code
        == 201
    )

    editado = client.post(
        f"/ui/clientes/todos/{comprador_id}",
        data={
            "nome": "Ana Compradora",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
            "cidade": "São Paulo",
        },
    )
    assert editado.status_code == 200
    assert "Ana Compradora" in editado.text
    assert "São Paulo" in editado.text

    busca = client.get("/ui/clientes/todos?q=Ana")
    assert "Ana Compradora" in busca.text
    assert "Caio Ambos" not in busca.text
    assert 'class="cell-mono" data-col="documento">123.456.789-01' in busca.text
    assert (
        'data-col="tipo"><span class="badge badge--plain badge--info">Pessoa Fisica'
        in busca.text
    )

    export = client.get("/ui/clientes/todos/exportar?q=Ana")
    assert export.status_code == 200
    assert (
        export.headers["content-disposition"] == 'attachment; filename="clientes.csv"'
    )
    assert export.text.splitlines()[0] == "ID,Nome,Documento,Tipo,Telefone,Cidade,UF"
    assert "Ana Compradora" in export.text
    assert "Caio Ambos" not in export.text

    modal_comprador = client.get(f"/ui/clientes/todos/{comprador_id}/veiculos")
    assert modal_comprador.status_code == 200
    assert "Veículos comprados" in modal_comprador.text
    assert "R$ 85.000,00" in modal_comprador.text

    modal_vendedor = client.get(f"/ui/clientes/todos/{vendedor_id}/veiculos")
    assert modal_vendedor.status_code == 200
    assert "Veículos vendidos" in modal_vendedor.text
    assert "R$ 80.000,00" in modal_vendedor.text

    todos = client.get("/ui/clientes/todos")
    assert todos.status_code == 200
    assert "Ana Compradora" in todos.text
    assert "Bia Vendedora" in todos.text
    assert "Caio Ambos" in todos.text
    assert "Dora Sem Vinculo" in todos.text

    modal_todos = client.get(f"/ui/clientes/todos/{ambos_id}/veiculos")
    assert modal_todos.status_code == 200
    assert "Veículos comprados" in modal_todos.text
    assert "Veículos vendidos" in modal_todos.text

    redirecionamento = client.get("/ui/clientes", follow_redirects=False)
    assert redirecionamento.status_code == 303
    assert redirecionamento.headers["location"] == "/ui/clientes/todos"


def test_ui_clientes_compradores_e_vendedores_nao_existem_mais(
    client: TestClient,
) -> None:
    assert client.get("/ui/clientes/compradores").status_code == 404
    assert client.get("/ui/clientes/vendedores").status_code == 404
    menu = client.get("/ui/clientes/todos").text
    assert "Clientes Compradores" not in menu
    assert "Clientes Vendedores" not in menu


def test_ui_clientes_e_compras_formatam_documento_e_telefone(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    pessoa_fisica_id = _criar_cliente(client, headers, "Ana CPF", "12345678901")
    edicao = client.post(
        f"/ui/clientes/todos/{pessoa_fisica_id}",
        data={
            "nome": "Ana CPF",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
            "telefone": "11999990000",
        },
    )
    assert edicao.status_code == 200, edicao.text
    client.post(
        "/clientes",
        json={
            "nome": "Empresa CNPJ",
            "documento": "12345678000102",
            "tipo": "pessoa_juridica",
        },
        headers=headers,
    )

    pagina_clientes = client.get("/ui/clientes/todos").text
    assert "123.456.789-01" in pagina_clientes
    assert "12.345.678/0001-02" in pagina_clientes
    assert "(11) 99999-0000" in pagina_clientes

    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    client.post(
        "/compras",
        json={
            "cliente_id": pessoa_fisica_id,
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-01",
            "valor_compra": "10000.00",
        },
        headers=headers,
    )
    pagina_compras = client.get("/ui/compras").text
    assert "123.456.789-01" in pagina_compras


def test_ui_clientes_documentos_modal_crud(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)

    cliente_id = _criar_cliente(client, headers, "João Documento", "98765432109")

    modal = client.get(f"/ui/clientes/{cliente_id}/documentos")
    assert modal.status_code == 200
    assert f'hx-post="/ui/clientes/{cliente_id}/documentos"' in modal.text
    assert 'type="file"' in modal.text
    assert "Enviar documentos" in modal.text

    upload = client.post(
        f"/ui/clientes/{cliente_id}/documentos",
        files=[
            ("documentos", ("comprovante.pdf", b"%PDF-conteudo-doc", "application/pdf"))
        ],
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
        assert salvo.content == b"%PDF-conteudo-doc"
    finally:
        with contextlib.suppress(FileNotFoundError):
            Path("bases/xtreme_system/api").joinpath(caminho.lstrip("/")).unlink()

    excluido = client.post(f"/ui/clientes/{cliente_id}/documentos/{doc_id}/excluir")
    assert excluido.status_code == 200
    assert "Nenhum documento" in excluido.text


def test_ui_action_icons_cores_e_oob_de_anexos(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    novo_veiculo = client.post(
        "/veiculos",
        json={
            "tipo": "moto",
            "modelo": "CG 160",
            "cor": "Vermelha",
            "ano": 2025,
            "placa": "XYZ1234",
            "km": 0,
            "preco": "15000.00",
            "investidor_id": investidor_id,
            "tipo_entrada": "consignacao",
        },
        headers=headers,
    )
    assert novo_veiculo.status_code == 201

    pagina_veiculos = client.get("/ui/veiculos").text
    assert "btn--focus" in pagina_veiculos
    assert "action-edit" in pagina_veiculos
    assert "action-user" in pagina_veiculos
    assert "action-view" in pagina_veiculos
    assert "badge--success badge--plain" in pagina_veiculos
    assert 'badge--info badge--plain">Compra<' in pagina_veiculos
    assert 'badge--warning badge--plain">Consignação<' in pagina_veiculos
    assert "btn--danger action-delete" not in pagina_veiculos
    assert f'hx-get="/ui/veiculos/{veiculo_id}/imagens"' in pagina_veiculos
    assert f'hx-get="/ui/veiculos/{veiculo_id}/procuracao"' in pagina_veiculos
    assert f'hx-get="/ui/veiculos/{veiculo_id}/comprovantes"' not in pagina_veiculos
    assert "action-image" not in _classes_do_botao(
        pagina_veiculos, f"action-veiculo-{veiculo_id}-imagens"
    )
    assert "action-file" not in _classes_do_botao(
        pagina_veiculos, f"action-veiculo-{veiculo_id}-procuracao"
    )

    upload_img = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto-cor.jpg", b"\xff\xd8\xfffoto", "image/jpeg")},
    )
    assert upload_img.status_code == 200
    assert 'hx-swap-oob="outerHTML"' in upload_img.text
    assert "action-image" in _classes_do_botao(
        upload_img.text, f"action-veiculo-{veiculo_id}-imagens"
    )

    img_id_match = re.search(
        r"/ui/veiculos/\d+/imagens/(?P<img_id>\d+)/excluir", upload_img.text
    )
    assert img_id_match is not None
    exclui_img = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens/{img_id_match.group('img_id')}/excluir"
    )
    assert exclui_img.status_code == 200
    assert "action-image" not in _classes_do_botao(
        exclui_img.text, f"action-veiculo-{veiculo_id}-imagens"
    )

    upload_proc = client.post(
        f"/ui/veiculos/{veiculo_id}/procuracao",
        files={"documentos": ("procuracao-cor.pdf", b"%PDF-proc", "application/pdf")},
    )
    assert upload_proc.status_code == 200
    assert "action-file" in _classes_do_botao(
        upload_proc.text, f"action-veiculo-{veiculo_id}-procuracao"
    )

    cliente_id = _criar_cliente(client, headers, "Cliente Cor", "12312312312")
    client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "data_venda": "2026-07-11",
            "valor_venda": "90000.00",
            "forma_pagamento": "pix",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    pagina_clientes = client.get("/ui/clientes/todos").text
    assert "action-file" not in _classes_do_botao(
        pagina_clientes, f"action-cliente-{cliente_id}-documentos"
    )

    upload_doc_cliente = client.post(
        f"/ui/clientes/{cliente_id}/documentos",
        files={"documentos": ("cliente-cor.pdf", b"%PDF-cliente", "application/pdf")},
    )
    assert upload_doc_cliente.status_code == 200
    assert "action-file" in _classes_do_botao(
        upload_doc_cliente.text, f"action-cliente-{cliente_id}-documentos"
    )

    pagina_vendas = client.get("/ui/vendas").text
    assert 'href="/ui/vendas/' in pagina_vendas
    assert "action-file" in pagina_vendas

    compra_id = _seed_compra(client, "32132132199")
    pagina_compras = client.get("/ui/compras").text
    assert "action-file" not in _classes_do_botao(
        pagina_compras, f"action-compra-{compra_id}-comprovantes"
    )

    upload_compra = client.post(
        f"/ui/compras/{compra_id}/comprovantes",
        files={
            "comprovantes": (
                "comprovante-cor.pdf",
                b"%PDF-comprovante",
                "application/pdf",
            )
        },
    )
    assert upload_compra.status_code == 200
    assert "action-file" in _classes_do_botao(
        upload_compra.text, f"action-compra-{compra_id}-comprovantes"
    )

    for resposta in (
        upload_img,
        upload_proc,
        upload_doc_cliente,
        upload_compra,
    ):
        _remover_uploads_renderizados(resposta.text)


def test_ui_investidores_crud_basico(client: TestClient) -> None:
    _login_admin(client)

    criado = client.post("/ui/investidores", data={"nome": "Nova Investidora"})
    assert criado.status_code == 200
    assert "Nova Investidora" in criado.text
    assert "cell-num" in criado.text
    assert "R$ 0,00" in criado.text


def test_ui_listas_administrativas_paginam_usuarios_perfis_investidores(
    client: TestClient,
) -> None:
    _login_admin(client)

    client.post(
        "/ui/usuarios",
        data={"username": "usuario pagina 1", "senha": "abc"},
    )
    client.post(
        "/ui/usuarios",
        data={"username": "usuario pagina 2", "senha": "abc"},
    )
    client.post("/ui/perfis", data={"nome": "Perfil pagina 1", "paginas": ["compras"]})
    client.post("/ui/perfis", data={"nome": "Perfil pagina 2", "paginas": ["vendas"]})
    client.post("/ui/investidores", data={"nome": "Investidor pagina 1"})
    client.post("/ui/investidores", data={"nome": "Investidor pagina 2"})

    for path, first_query, second_query, page_start in (
        (
            "/ui/usuarios",
            "sort=username&limit=1&offset=1",
            "sort=username&limit=1&offset=2",
            2,
        ),
        (
            "/ui/perfis",
            "limit=1&offset=0",
            "limit=1&offset=1",
            1,
        ),
        (
            "/ui/investidores",
            "limit=1&offset=1",
            "limit=1&offset=2",
            2,
        ),
    ):
        primeira = client.get(f"{path}?{first_query}")
        segunda = client.get(f"{path}?{second_query}")

        assert primeira.status_code == 200
        assert f"Mostrando {page_start}" in primeira.text
        assert "Próxima" in primeira.text
        primeira_linhas = re.findall(r'id="(?:usuario|item)-\d+"', primeira.text)
        assert len(primeira_linhas) == 1

        assert segunda.status_code == 200
        assert f"Mostrando {page_start + 1}" in segunda.text
        assert "Anterior" in segunda.text
        segunda_linhas = re.findall(r'id="(?:usuario|item)-\d+"', segunda.text)
        assert len(segunda_linhas) == 1
        assert primeira_linhas != segunda_linhas


def test_ui_investidor_criar_rejeita_aporte_inicial_invalido(
    client: TestClient,
) -> None:
    _login_admin(client)

    resp = client.post(
        "/ui/investidores",
        data={"nome": "Investidor Com Aporte Inválido", "valor_investido": "1.234,56"},
    )

    assert resp.status_code == 400
    assert "Valor investido inválido" in resp.text
    assert "Investidor Com Aporte Inválido" not in client.get("/ui/investidores").text


def test_ui_investidor_criar_falha_se_aporte_inicial_falhar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="admin", senha="senha", papel=usuario.Papel.admin
            ),
        )

        def override() -> Iterator[Session]:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

        def fail_create(
            _session: Session, _data: caixa.LancamentoInvestimentoCreate
        ) -> caixa.LancamentoInvestimento:
            msg = "falha ao salvar aporte"
            raise RuntimeError(msg)

        app.dependency_overrides[get_session] = override
        monkeypatch.setattr(caixa, "create", fail_create)
        try:
            with TestClient(app, raise_server_exceptions=False) as test_client:
                _login_admin(test_client)
                resp = test_client.post(
                    "/ui/investidores",
                    data={"nome": "Investidor Com Aporte", "valor_investido": "10.00"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 500
        assert investidor.list_all(session) == []
    engine.dispose()


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
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", criado.text)
    assert "/07/2026" not in criado.text

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


def test_ui_atualizar_venda_preserva_dados_submetidos_em_erro(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    cliente_id = _criar_cliente(client, headers, "Cliente Venda Erro", "98765432101")
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    criada = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "pendente",
        },
    )
    assert criada.status_code == 200
    venda_id = client.get("/vendas", headers=headers).json()[0]["id"]

    resp = client.post(
        f"/ui/vendas/{venda_id}",
        data={
            "km": "12345",
            "valor_venda": "valor inválido",
            "valor_entrada": "15000.00",
            "debitos": "250.00",
            "forma_pagamento": "pix",
            "parcelas": "12",
            "status": "aprovado",
            "valor_diferenca": "500.00",
            "pagamento_pendente": "1",
            "valor_pendente": "100.00",
            "datas_pagamento": "10/08, 10/09",
            "observacoes": "observações editadas",
        },
    )

    assert resp.status_code == 400
    assert 'name="valor_venda"' in resp.text
    assert 'value="valor inválido"' in resp.text
    assert 'value="15000.00"' in resp.text
    assert 'value="pix"' in resp.text
    assert 'value="12"' in resp.text
    assert 'value="aprovado" selected' in resp.text
    assert 'value="100.00"' in resp.text
    assert 'value="10/08, 10/09"' in resp.text
    assert "observações editadas" in resp.text


def test_ui_atualizar_venda_preserva_dados_submetidos_em_conflito(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    cliente_id = _criar_cliente(
        client, headers, "Cliente Venda Conflito", "98765432102"
    )
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    criada = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "pendente",
        },
    )
    assert criada.status_code == 200
    venda_id = client.get("/vendas", headers=headers).json()[0]["id"]
    next(app.dependency_overrides[get_session]()).commit()

    def falhar_ao_atualizar(
        _session: Session,
        _obj: venda.Venda,
        _data: venda.VendaUpdate,
        _actor_id: int | None = None,
    ) -> venda.Venda:
        raise IntegrityError("UPDATE", {}, RuntimeError("venda duplicada"))

    monkeypatch.setattr(venda, "update", falhar_ao_atualizar)
    resp = client.post(
        f"/ui/vendas/{venda_id}",
        data={
            "valor_venda": "99000.00",
            "forma_pagamento": "pix",
            "parcelas": "2",
            "status": "aprovado",
        },
    )

    assert resp.status_code == 409
    assert 'value="99000.00"' in resp.text
    assert 'value="pix"' in resp.text
    assert 'value="2"' in resp.text
    assert 'value="aprovado" selected' in resp.text


def test_ctx_form_venda_carrega_clientes_para_o_select_e_nao_veiculos(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    calls: list[tuple[str, int | None]] = []

    def fake_clientes(
        _session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[cliente.Cliente]:
        assert offset == 0
        calls.append(("clientes", limit))
        return []

    def fake_veiculos(
        _session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[veiculo.Veiculo]:
        assert offset == 0
        calls.append(("veiculos", limit))
        return []

    monkeypatch.setattr(cliente, "list_all", fake_clientes)
    monkeypatch.setattr(veiculo, "list_all", fake_veiculos)

    _login_admin(client)
    resp = client.get("/ui/vendas/novo")

    assert resp.status_code == 200
    assert calls == [("clientes", None)]


def test_ctx_form_veiculo_nao_carrega_frota_nem_referencias(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _login_admin(client)
    calls: list[str] = []

    def fail(name: str) -> Callable[..., list[Any]]:
        def _fail(*_args: Any, **_kwargs: Any) -> list[Any]:
            calls.append(name)
            return []

        return _fail

    monkeypatch.setattr(veiculo, "list_ids", fail("veiculo.list_ids"))
    monkeypatch.setattr(cliente, "list_all", fail("cliente.list_all"))
    monkeypatch.setattr(investidor, "list_all", fail("investidor.list_all"))
    monkeypatch.setattr(
        compra,
        "latest_debitos_by_veiculo_ids",
        fail("compra.latest_debitos_by_veiculo_ids"),
    )

    resp = client.get("/ui/veiculos/novo")

    assert resp.status_code == 200
    assert calls == []
    assert 'data-reference-url="/ui/veiculos/referencias/clientes"' in resp.text
    assert 'data-reference-url="/ui/veiculos/referencias/investidores"' in resp.text

    edit = client.get("/ui/veiculos/1/editar")
    assert edit.status_code == 200
    assert 'value="Investidor A"' in edit.text
    assert calls == []


def test_ui_veiculo_referencias_busca_investidores(client: TestClient) -> None:
    _login_admin(client)

    resp = client.get("/ui/veiculos/referencias/investidores?q=Investidor&limit=1")

    assert resp.status_code == 200
    assert resp.json()["items"] == [{"id": 1, "label": "Investidor A"}]


def test_ui_venda_referencias_busca_e_pagina(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    cliente_a = _criar_cliente(client, headers, "Cliente A", "11111111111")
    cliente_b = _criar_cliente(client, headers, "Cliente B", "22222222222")

    primeira = client.get("/ui/vendas/referencias/clientes?q=Cliente&limit=1&offset=0")
    assert primeira.status_code == 200
    assert primeira.json()["items"] == [
        {"id": cliente_a, "label": "Cliente A (11111111111)"}
    ]
    assert primeira.json()["has_more"] is True

    segunda = client.get("/ui/vendas/referencias/clientes?q=Cliente&limit=1&offset=1")
    assert segunda.status_code == 200
    assert segunda.json()["items"] == [
        {"id": cliente_b, "label": "Cliente B (22222222222)"}
    ]

    veiculos = client.get("/ui/vendas/referencias/veiculos?limit=1")
    assert veiculos.status_code == 200
    assert len(veiculos.json()["items"]) == 1


def test_ui_nova_venda_exibe_select_de_veiculos_sem_paginacao(
    client: TestClient,
) -> None:
    _login_admin(client)

    resp = client.get("/ui/vendas/novo")

    assert resp.status_code == 200
    assert 'id="veiculo-select"' in resp.text
    assert 'name="veiculo_id" required' in resp.text
    assert '<option value="1">ABC1234 — Onix</option>' in resp.text
    assert 'data-reference-list="veiculos-list"' not in resp.text


def test_ui_nova_venda_exibe_cadastro_inline_de_troca_com_campos_obrigatorios(
    client: TestClient,
) -> None:
    _login_admin(client)

    resp = client.get("/ui/vendas/novo")

    assert resp.status_code == 200
    assert 'name="houve_troca"' in resp.text
    assert 'id="cadastrar-veiculo-troca"' in resp.text
    assert "Cadastrar novo veículo" in resp.text
    assert 'data-reference-list="veiculos-troca-list"' not in resp.text
    assert re.search(r'id="veiculo-troca-input"[^>]*data-reference-autoload', resp.text)
    assert resp.text.count('name="veic_troca_tipo" required') == 1
    for campo in (
        "veic_troca_placa",
        "veic_troca_modelo",
        "veic_troca_cor",
        "veic_troca_ano",
        "veic_troca_preco",
        "veic_troca_investidor_id",
    ):
        assert re.search(
            rf'<(?:input|select)[^>]*name="{campo}"[^>]*required', resp.text
        )


def test_ui_criar_venda_cadastra_veiculo_novo_na_troca(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    inv_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    cliente_id = _criar_cliente(client, headers, "Cliente Troca", "11122233344")

    criado = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "a_vista",
            "parcelas": "1",
            "status": "pendente",
            "houve_troca": "1",
            "veiculo_troca_novo": "1",
            "veiculo_troca_label": "ABC1234",
            "veic_troca_tipo": "carro",
            "veic_troca_placa": "TRC1234",
            "veic_troca_modelo": "Gol",
            "veic_troca_cor": "Branco",
            "veic_troca_ano": "2018",
            "veic_troca_km": "60000",
            "veic_troca_preco": "30000.00",
            "veic_troca_investidor_id": str(inv_id),
            "valor_diferenca": "55000.00",
        },
    )

    assert criado.status_code == 200, criado.text
    veiculos = client.get("/veiculos", headers=headers).json()
    veiculo_troca = next(v for v in veiculos if v["placa"] == "TRC1234")
    assert veiculo_troca["modelo"] == "Gol"
    assert veiculo_troca["tipo_entrada"] == "compra"
    assert veiculo_troca["status"] == "disponivel"

    vendas = client.get("/vendas", headers=headers).json()
    venda_criada = next(v for v in vendas if v["veiculo"]["id"] == veiculo_id)
    assert venda_criada["veiculo_troca"]["placa"] == "TRC1234"


def test_ui_criar_venda_troca_placa_ja_cadastrada_retorna_erro(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    inv_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    cliente_id = _criar_cliente(client, headers, "Cliente Troca Dup", "55566677788")

    resp = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "a_vista",
            "parcelas": "1",
            "status": "pendente",
            "houve_troca": "1",
            "veiculo_troca_novo": "1",
            "veiculo_troca_label": "ABC1234",
            "veic_troca_tipo": "carro",
            "veic_troca_placa": "ABC1234",
            "veic_troca_modelo": "Onix",
            "veic_troca_cor": "Prata",
            "veic_troca_ano": "2024",
            "veic_troca_preco": "30000.00",
            "veic_troca_investidor_id": str(inv_id),
        },
    )

    assert resp.status_code == 400
    assert "Placa já cadastrada" in resp.text
    assert 'name="houve_troca" value="1" type="checkbox" checked' in resp.text
    assert 'name="veiculo_troca_novo" value="1"' in resp.text
    assert 'name="veic_troca_placa" value="ABC1234"' in resp.text
    assert client.get("/vendas", headers=headers).json() == []


def test_ui_criar_venda_respeita_limit_da_listagem(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    inv_id = client.get("/investidores", headers=headers).json()[0]["id"]

    veiculo_ids = []
    for indice in range(3):
        cliente_id = _criar_cliente(
            client, headers, f"Cliente {indice}", f"1000000000{indice}"
        )
        vei = client.post(
            "/veiculos",
            json={
                "tipo": "carro",
                "modelo": "Onix",
                "cor": "Prata",
                "ano": 2024,
                "placa": f"LIM{indice}999",
                "km": 12000,
                "preco": "85000.00",
                "investidor_id": inv_id,
            },
            headers=headers,
        )
        assert vei.status_code == 201, vei.text
        veiculo_id = vei.json()["id"]
        veiculo_ids.append(veiculo_id)
        resp = client.post(
            "/vendas",
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "data_venda": f"2026-07-0{indice + 1}",
                "valor_venda": "85000.00",
                "forma_pagamento": "a_vista",
                "parcelas": 1,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    novo_cliente_id = _criar_cliente(client, headers, "Cliente Novo", "10000000009")
    criado = client.post(
        "/ui/vendas?limit=2",
        data={
            "cliente_id": str(novo_cliente_id),
            "veiculo_id": str(client.get("/veiculos", headers=headers).json()[0]["id"]),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "a_vista",
            "parcelas": "1",
            "status": "pendente",
        },
    )

    assert criado.status_code == 200
    assert len(re.findall(r'<tr id="venda-', criado.text)) == 2


def test_ui_atualizar_venda_registra_autor_na_auditoria(
    make_client: Callable[..., TestClient],
) -> None:
    sessions: dict[str, Session] = {}

    def seed(session: Session) -> None:
        sessions["session"] = session
        _seed_investidor_e_veiculo(session)

    client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=seed,
    )
    _login_admin(client)
    headers = _admin_headers(client)
    admin_id = next(
        u["id"]
        for u in client.get("/usuarios", headers=headers).json()
        if u["username"] == "admin"
    )
    cliente_id = _criar_cliente(client, headers, "Carlos Lima", "98765432100")
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    criado = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "85000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "pendente",
        },
    )
    assert criado.status_code == 200
    venda_id = client.get("/vendas", headers=headers).json()[0]["id"]

    editado = client.post(
        f"/ui/vendas/{venda_id}",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-09",
            "valor_venda": "86000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "aprovado",
        },
    )

    assert editado.status_code == 200
    rows = auditoria.query(
        sessions["session"], tabela="venda", tipo_acao="UPDATE", limit=100
    )
    assert rows
    assert rows[0].usuario_id == admin_id


def test_ui_atualizar_veiculo_registra_autor_na_auditoria_do_lancamento(
    make_client: Callable[..., TestClient],
) -> None:
    sessions: dict[str, Session] = {}

    def seed(session: Session) -> None:
        sessions["session"] = session
        _seed_investidor_e_veiculo(session)
        veiculo_obj = veiculo.list_all(session)[0]
        caixa.criar_lancamento_veiculo(session, veiculo_obj)

    client = make_client(
        usuarios=[("admin", usuario.Papel.admin)],
        invoke_post_commit=True,
        seed=seed,
    )
    _login_admin(client)
    headers = _admin_headers(client)
    admin_id = next(
        u["id"]
        for u in client.get("/usuarios", headers=headers).json()
        if u["username"] == "admin"
    )
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]

    editado = client.post(
        f"/ui/veiculos/{veiculo_id}",
        data={
            "tipo": "carro",
            "modelo": "Onix",
            "cor": "Prata",
            "ano": "2024",
            "placa": "ABC1234",
            "km": "12000",
            "preco": "86000.00",
            "investidor_id": str(investidor_id),
            "status": "disponivel",
        },
    )

    assert editado.status_code == 200
    rows = auditoria.query(
        sessions["session"],
        tabela="lancamento_investimento",
        tipo_acao="UPDATE",
        limit=100,
    )
    assert rows
    assert rows[0].usuario_id == admin_id


def test_ui_vendas_rejeita_veiculo_indisponivel_na_edicao(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)

    cliente_id = _criar_cliente(client, headers, "Cliente UI", "33333333333")
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_disponivel = client.get("/veiculos", headers=headers).json()[0]["id"]
    veiculo_indisponivel = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Corolla",
            "cor": "Preto",
            "ano": 2021,
            "placa": "UIX9A99",
            "km": 15000,
            "preco": "95000.00",
            "investidor_id": investidor_id,
        },
        headers=headers,
    )
    assert veiculo_indisponivel.status_code == 201
    veiculo_indisponivel_id = veiculo_indisponivel.json()["id"]

    venda_concluida = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_indisponivel_id,
            "data_venda": "2026-07-09",
            "valor_venda": "98000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    assert venda_concluida.status_code == 201

    criada = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_disponivel),
            "data_venda": "2026-07-10",
            "valor_venda": "85000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "pendente",
        },
    )
    assert criada.status_code == 200

    venda_id = next(
        item["id"]
        for item in client.get("/vendas", headers=headers).json()
        if item["cliente"]["id"] == cliente_id
        and item["veiculo"]["id"] == veiculo_disponivel
    )

    resp = client.post(
        f"/ui/vendas/{venda_id}",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_indisponivel_id),
            "data_venda": "2026-07-10",
            "valor_venda": "85000.00",
            "forma_pagamento": "financiamento",
            "parcelas": "36",
            "status": "pendente",
        },
    )

    assert resp.status_code == 400
    assert "indisponível" in resp.text
    venda_atual = client.get(f"/vendas/{venda_id}", headers=headers)
    assert venda_atual.status_code == 200
    assert venda_atual.json()["veiculo"]["id"] == veiculo_disponivel


def test_ui_atualizar_venda_concluida_para_pendente_reserva_veiculo(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)

    cliente_id = _criar_cliente(client, headers, "Cliente Reversao", "44444444444")
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    criada = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-10",
            "valor_venda": "85000.00",
            "forma_pagamento": "a_vista",
            "parcelas": "1",
            "status": "concluido",
        },
    )
    assert criada.status_code == 200
    assert (
        client.get(f"/veiculos/{veiculo_id}", headers=headers).json()["status"]
        == "vendido"
    )

    venda_id = next(
        item["id"]
        for item in client.get("/vendas", headers=headers).json()
        if item["cliente"]["id"] == cliente_id
    )
    atualizada = client.post(
        f"/ui/vendas/{venda_id}",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-10",
            "valor_venda": "85000.00",
            "forma_pagamento": "a_vista",
            "parcelas": "1",
            "status": "pendente",
        },
    )

    assert atualizada.status_code == 200
    assert (
        client.get(f"/veiculos/{veiculo_id}", headers=headers).json()["status"]
        == "reservado"
    )


def test_ui_vendas_busca_por_cliente_nao_duplica_resultados(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    base_veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_resp = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Civic",
            "cor": "Preto",
            "ano": 2020,
            "placa": "XYZ9G87",
            "km": 10000,
            "preco": "80000.00",
            "investidor_id": investidor_id,
        },
        headers=headers,
    )
    assert veiculo_resp.status_code == 201
    veiculo_id = veiculo_resp.json()["id"]

    ana_id = _criar_cliente(client, headers, "Ana Busca", "11111111111")
    bia_id = _criar_cliente(client, headers, "Bia Busca", "22222222222")

    assert (
        client.post(
            "/vendas",
            json={
                "cliente_id": ana_id,
                "veiculo_id": base_veiculo_id,
                "data_venda": "2026-07-09",
                "valor_venda": "85000.00",
                "forma_pagamento": "pix",
                "parcelas": 1,
                "status": "concluido",
            },
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/vendas",
            json={
                "cliente_id": bia_id,
                "veiculo_id": veiculo_id,
                "data_venda": "2026-07-10",
                "valor_venda": "86000.00",
                "forma_pagamento": "pix",
                "parcelas": 1,
                "status": "pendente",
            },
            headers=headers,
        ).status_code
        == 201
    )

    busca = client.get("/ui/vendas?q=Ana")
    assert busca.status_code == 200
    assert "Ana Busca" in busca.text
    assert "Bia Busca" not in busca.text


def test_ui_vendas_sem_tabela_de_fechamento_nao_quebra(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    monkeypatch.setattr(fechamento_venda, "_schema_disponivel", lambda _session: False)

    pagina = client.get("/ui/vendas")

    assert pagina.status_code == 200
    assert 'id="linhas"' in pagina.text


def test_venda_inline_cliente_nao_persiste_quando_validacao_falha() -> None:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
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
                placa="XYZ9999",
                km=12000,
                preco=85000,
                investidor_id=inv.id,
            ),
        )

        def override() -> Iterator[Session]:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app, raise_server_exceptions=False) as test_client:
                _login_admin(test_client)
                resp = test_client.post(
                    "/ui/vendas",
                    data={
                        "cli_nome": "Cliente Fantasma",
                        "cli_documento": "00011122233",
                        "cli_tipo": "pessoa_fisica",
                        "veiculo_id": "99999",
                        "data_venda": "2026-07-15",
                        "valor_venda": "50000.00",
                        "forma_pagamento": "financiamento",
                        "parcelas": "36",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert cliente.get_by_documento(session, "00011122233") is None
    engine.dispose()


def test_resolver_cliente_compartilhado_cobre_ramos_principais() -> None:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
        existente = cliente.create(
            session,
            cliente.ClienteCreate(
                nome="Cliente Existente",
                documento="12345678901",
                tipo=cliente.TipoCliente.pessoa_fisica,
            ),
        )

        cliente_obj, novo_cliente_data, erro = resolver_cliente(
            session, {"cliente_id": str(existente.id)}
        )
        assert cliente_obj is not None
        assert cliente_obj.id == existente.id
        assert novo_cliente_data is None
        assert erro is None

        cliente_obj, novo_cliente_data, erro = resolver_cliente(
            session, {"cliente_id": "99999"}
        )
        assert cliente_obj is None
        assert novo_cliente_data is None
        assert erro == "Cliente inválido ou inexistente"

        cliente_obj, novo_cliente_data, erro = resolver_cliente(
            session,
            {
                "cli_nome": "Duplicado",
                "cli_documento": existente.documento,
                "cli_tipo": "pessoa_fisica",
            },
        )
        assert cliente_obj is None
        assert novo_cliente_data is None
        assert erro == "CPF já cadastrado — selecione o cliente na lista"

        cliente_obj, novo_cliente_data, erro = resolver_cliente(
            session,
            {
                "cli_nome": "Cliente Novo",
                "cli_documento": "10987654321",
                "cli_tipo": "pessoa_fisica",
                "cli_email": "novo@example.com",
            },
        )
        assert cliente_obj is None
        assert novo_cliente_data is not None
        assert novo_cliente_data.nome == "Cliente Novo"
        assert novo_cliente_data.documento == "10987654321"
        assert novo_cliente_data.email == "novo@example.com"
        assert erro is None
    engine.dispose()


def test_ui_compras_crud_basico(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)

    pagina = client.get("/ui/compras")
    assert pagina.status_code == 200
    assert 'id="linhas"' in pagina.text

    formulario = client.get("/ui/compras/novo")
    assert formulario.status_code == 200
    assert 'name="idempotency_key"' in formulario.text
    assert 'hx-sync="this:drop"' in formulario.text
    assert "hx-disabled-elt=\"find button[type='submit']\"" in formulario.text

    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_resp = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "tipo_entrada": "compra",
            "placa": "CMP1A23",
            "modelo": "Corolla",
            "cor": "Preto",
            "ano": 2022,
            "km": 30000,
            "preco": "84000.00",
            "investidor_id": investidor_id,
        },
        headers=headers,
    )
    assert veiculo_resp.status_code == 201
    veiculo_id = veiculo_resp.json()["id"]

    cliente_resp = client.post(
        "/clientes",
        json={
            "nome": "Carlos Compra",
            "documento": "45678912300",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert cliente_resp.status_code == 201
    cliente_id = cliente_resp.json()["id"]

    criado = client.post(
        "/ui/compras",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "idempotency_key": "compra-submit-1",
            "data_compra": "2026-07-09",
            "valor_compra": "84000.00",
            "debitos": "500.00",
        },
    )
    assert criado.status_code == 200

    duplicado = client.post(
        "/ui/compras",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "idempotency_key": "compra-submit-1",
            "data_compra": "2026-07-09",
            "valor_compra": "84000.00",
            "debitos": "500.00",
        },
    )
    assert duplicado.status_code == 200

    compras = client.get("/compras", headers=headers).json()
    assert len(compras) == 1
    compra = compras[0]
    compra_id = compra["id"]

    editado = client.post(
        f"/ui/compras/{compra_id}",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_compra": "2026-07-09",
            "valor_compra": "83000.00",
            "debitos": "",
            "observacoes": "ajustada",
        },
    )
    assert editado.status_code == 200
    assert "ajustada" in editado.text
    assert "R$ 83.000,00" in editado.text
    assert 'badge badge--plain badge--warning">' in editado.text

    excluido = client.post(f"/ui/compras/{compra_id}/excluir")
    assert excluido.status_code == 200
    assert "Carlos Compra" not in excluido.text
    auditoria_resp = client.get(
        "/auditoria",
        params={"tabela": "veiculo", "tipo_acao": "DELETE"},
        headers=_admin_headers(client),
    )
    assert auditoria_resp.status_code == 200
    assert [row["registro_id"] for row in auditoria_resp.json()] == [veiculo_id]
    csv_resp = client.get("/ui/compras/exportar")
    assert csv_resp.status_code == 200
    assert (
        csv_resp.headers["content-disposition"] == 'attachment; filename="compras.csv"'
    )
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Carlos Compra" not in csv_resp.text


def test_ui_nova_compra_renderiza_clientes_cadastrados(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    cliente_id = _criar_cliente(client, headers, "Cliente Compra Select", "45678912301")

    formulario = client.get("/ui/compras/novo")

    assert formulario.status_code == 200
    assert formulario.headers["cache-control"] == "no-store"
    assert (
        f'<option value="{cliente_id}">Cliente Compra Select · 45678912301</option>'
        in formulario.text
    )


def test_ui_compra_conflito_de_idempotencia_nao_duplica_compra_nem_caixa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _client_with_failing_final_commit() as (client, session, _fail_commit):
        _login_admin(client)
        headers = _admin_headers(client)
        veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
        veiculo_obj = veiculo.get(session, veiculo_id)
        assert veiculo_obj is not None
        caixa.criar_lancamento_veiculo(session, veiculo_obj)
        cliente_id = _criar_cliente(
            client, headers, "Cliente Idempotente", "45678912301"
        )
        dados = {
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "idempotency_key": "compra-race-1",
            "data_compra": "2026-07-09",
            "valor_compra": "84000.00",
        }

        primeira = client.post("/ui/compras", data=dados)
        assert primeira.status_code == 200

        lookup_original = compra.get_by_idempotency_key
        lookup_calls = 0

        def lookup_com_race(session: Session, key: str) -> compra.Compra | None:
            nonlocal lookup_calls
            lookup_calls += 1
            if lookup_calls == 1:
                return None
            return lookup_original(session, key)

        monkeypatch.setattr(compra, "get_by_idempotency_key", lookup_com_race)

        segunda = client.post("/ui/compras", data=dados)

        assert segunda.status_code == 200
        assert lookup_calls == 2
        assert len(compra.list_all(session)) == 1
        assert len(caixa.list_all(session)) == 1


def test_ui_compra_de_veiculo_novo_separa_preco_anunciado_do_custo(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    cliente_resp = client.post(
        "/clientes",
        json={
            "nome": "Vendedor Novo Veículo",
            "documento": "45678912301",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert cliente_resp.status_code == 201

    criado = client.post(
        "/ui/compras",
        data={
            "cliente_id": str(cliente_resp.json()["id"]),
            "vei_tipo": "carro",
            "vei_tipo_entrada": "compra",
            "vei_placa": "NOV1A23",
            "vei_modelo": "Civic",
            "vei_cor": "Preto",
            "vei_ano": "2024",
            "vei_investidor_id": str(investidor_id),
            "data_compra": "2026-08-03",
            "valor_compra": "73000.00",
        },
    )
    assert criado.status_code == 200

    veiculo_criado = next(
        item
        for item in client.get("/veiculos", headers=headers).json()
        if item["placa"] == "NOV1A23"
    )
    assert veiculo_criado["preco"] is None

    compra_criada = next(
        item
        for item in client.get("/compras", headers=headers).json()
        if item["veiculo"]["placa"] == "NOV1A23"
    )
    assert compra_criada["valor_compra"] == "73000.00"


def test_ctx_lista_compras_busca_comprovantes_em_lote(db_session: Session) -> None:
    inv = investidor.create(db_session, investidor.InvestidorCreate(nome="Lote"))
    cliente_obj = cliente.create(
        db_session,
        cliente.ClienteCreate(
            nome="Cliente Lote",
            documento="98765432100",
            tipo=cliente.TipoCliente.pessoa_fisica,
        ),
    )
    compras: list[compra.Compra] = []
    for idx in range(3):
        veiculo_obj = veiculo.create(
            db_session,
            veiculo.VeiculoCreate(
                tipo=veiculo.TipoVeiculo.carro,
                modelo=f"Modelo {idx}",
                cor="Prata",
                ano=2024,
                placa=f"LOT{idx}123",
                km=1000 + idx,
                preco=80000,
                investidor_id=inv.id,
            ),
        )
        compras.append(
            compra.create(
                db_session,
                compra.CompraCreate(
                    cliente_id=cliente_obj.id,
                    veiculo_id=veiculo_obj.id,
                    data_compra="2026-07-09",
                    valor_compra=79000,
                ),
            )
        )
    imagem_comprovante_compra.create(
        db_session,
        imagem_comprovante_compra.ImagemComprovanteCompraCreate(
            compra_id=compras[0].id,
            url="/static/uploads/compras/1/comprovantes/a.pdf",
        ),
    )
    imagem_comprovante_compra.create(
        db_session,
        imagem_comprovante_compra.ImagemComprovanteCompraCreate(
            compra_id=compras[2].id,
            url="/static/uploads/compras/3/comprovantes/c.pdf",
        ),
    )
    db_session.flush()
    engine = db_session.get_bind()
    assert isinstance(engine, Engine)
    selects = 0

    def count_comprovantes_selects(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        nonlocal selects
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "imagem_comprovante_compra" in statement
        ):
            selects += 1

    event.listen(engine, "before_cursor_execute", count_comprovantes_selects)
    try:
        ctx = compras_ui._ctx_lista_compras(db_session, compras)  # noqa: SLF001
    finally:
        event.remove(engine, "before_cursor_execute", count_comprovantes_selects)

    comprovantes_por_compra = ctx["comprovantes_por_compra"]
    assert selects == 1
    assert [item.url for item in comprovantes_por_compra[compras[0].id]] == [
        "/static/uploads/compras/1/comprovantes/a.pdf"
    ]
    assert comprovantes_por_compra[compras[1].id] == []
    assert [item.url for item in comprovantes_por_compra[compras[2].id]] == [
        "/static/uploads/compras/3/comprovantes/c.pdf"
    ]


def test_ui_compras_rollback_em_integrityerror_de_veiculo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="admin", senha="senha", papel=usuario.Papel.admin
            ),
        )
        inv = investidor.create(
            session, investidor.InvestidorCreate(nome="Investidor A")
        )
        cliente_existente = cliente.create(
            session,
            cliente.ClienteCreate(
                nome="Cliente Existente",
                documento="12345678901",
                tipo=cliente.TipoCliente.pessoa_fisica,
            ),
        )

        def override() -> Iterator[Session]:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

        def fail_create(
            _session: Session,
            _data: veiculo.VeiculoCreate,
            _actor_id: int | None = None,
        ) -> veiculo.Veiculo:
            raise IntegrityError("", {}, Exception("veiculo duplicado"))

        app.dependency_overrides[get_session] = override
        monkeypatch.setattr(veiculo, "create", fail_create)
        try:
            with TestClient(app, raise_server_exceptions=False) as test_client:
                _login_admin(test_client)
                resp = test_client.post(
                    "/ui/compras",
                    data={
                        "cliente_id": str(cliente_existente.id),
                        "vei_tipo": "carro",
                        "vei_tipo_entrada": "compra",
                        "vei_placa": "NEW1234",
                        "vei_modelo": "Civic",
                        "vei_cor": "Preto",
                        "vei_ano": "2024",
                        "vei_km": "12000",
                        "vei_preco": "85000.00",
                        "vei_investidor_id": str(inv.id),
                        "data_compra": "2026-07-09",
                        "valor_compra": "85000.00",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409
        assert "Veículo já existe" in resp.text
        assert compra.list_all(session) == []
    engine.dispose()


def test_ui_compras_busca_por_cliente_nao_duplica_resultados(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    base_veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
    veiculo_resp = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Civic",
            "cor": "Preto",
            "ano": 2020,
            "placa": "XYZ9G88",
            "km": 10000,
            "preco": "80000.00",
            "investidor_id": investidor_id,
        },
        headers=headers,
    )
    assert veiculo_resp.status_code == 201
    veiculo_id = veiculo_resp.json()["id"]

    ana_id = _criar_cliente(client, headers, "Ana Compra", "33333333333")
    bia_id = _criar_cliente(client, headers, "Bia Compra", "44444444444")

    assert (
        client.post(
            "/compras",
            json={
                "cliente_id": ana_id,
                "veiculo_id": base_veiculo_id,
                "data_compra": "2026-07-09",
                "valor_compra": "84000.00",
            },
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/compras",
            json={
                "cliente_id": bia_id,
                "veiculo_id": veiculo_id,
                "data_compra": "2026-07-10",
                "valor_compra": "83000.00",
            },
            headers=headers,
        ).status_code
        == 201
    )

    busca = client.get("/ui/compras?q=Ana")
    assert busca.status_code == 200
    assert "Ana Compra" in busca.text
    assert "Bia Compra" not in busca.text


def test_ui_compras_comprovantes_modal_crud(client: TestClient) -> None:
    _login_admin(client)
    compra_id = _seed_compra(client, "45678912311")

    modal = client.get(f"/ui/compras/{compra_id}/comprovantes")
    assert modal.status_code == 200
    assert f'hx-post="/ui/compras/{compra_id}/comprovantes"' in modal.text
    assert 'type="file"' in modal.text

    upload = client.post(
        f"/ui/compras/{compra_id}/comprovantes",
        files=[
            (
                "comprovantes",
                ("comprovante.pdf", b"%PDF-conteudo-pagto", "application/pdf"),
            )
        ],
    )
    assert upload.status_code == 200
    assert "/static/uploads/compras/" in upload.text

    match = re.search(
        r'hx-post="/ui/compras/\d+/comprovantes/(?P<comp_id>\d+)/excluir"',
        upload.text,
    )
    assert match is not None
    comprovante_id = match.group("comp_id")

    arquivo = re.search(
        r"(?P<url>/static/uploads/compras/\d+/comprovantes/[a-f0-9]+\.pdf)",
        upload.text,
    )
    assert arquivo is not None
    caminho = Path("bases/xtreme_system/api").joinpath(arquivo.group("url").lstrip("/"))
    try:
        assert caminho.read_bytes() == b"%PDF-conteudo-pagto"

        excluido = client.post(
            f"/ui/compras/{compra_id}/comprovantes/{comprovante_id}/excluir"
        )
        assert excluido.status_code == 200
        assert "Nenhum comprovante" in excluido.text
        assert not caminho.exists()
    finally:
        with contextlib.suppress(FileNotFoundError):
            caminho.unlink()

    upload_para_excluir_compra = client.post(
        f"/ui/compras/{compra_id}/comprovantes",
        files=[
            (
                "comprovantes",
                ("comprovante2.pdf", b"%PDF-conteudo-pagto-2", "application/pdf"),
            )
        ],
    )
    outro_arquivo = re.search(
        r"(?P<url>/static/uploads/compras/\d+/comprovantes/[a-f0-9]+\.pdf)",
        upload_para_excluir_compra.text,
    )
    assert outro_arquivo is not None
    outro_caminho = Path("bases/xtreme_system/api").joinpath(
        outro_arquivo.group("url").lstrip("/")
    )
    try:
        assert outro_caminho.exists()

        compra_excluida = client.post(f"/ui/compras/{compra_id}/excluir")
        assert compra_excluida.status_code == 200
        assert not outro_caminho.exists()
    finally:
        with contextlib.suppress(FileNotFoundError):
            outro_caminho.unlink()


def test_modal_com_anexo_respeita_disponibilidade_do_arquivo(
    client: TestClient,
) -> None:
    _login_admin(client)
    compra_id = _seed_compra(client, "65498732100")

    upload = client.post(
        f"/ui/compras/{compra_id}/comprovantes",
        files=[
            (
                "comprovantes",
                ("comprovante.pdf", b"%PDF-conteudo-pagto", "application/pdf"),
            )
        ],
    )

    assert upload.status_code == 200
    arquivo = re.search(
        r"(?P<url>/static/uploads/compras/\d+/comprovantes/[a-f0-9]+\.pdf)",
        upload.text,
    )
    assert arquivo is not None
    caminho = Path("bases/xtreme_system/api").joinpath(arquivo.group("url").lstrip("/"))
    try:
        assert caminho.exists()
        caminho.unlink()
        modal = client.get(f"/ui/compras/{compra_id}/comprovantes")
        assert modal.status_code == 200
        assert "mmgr__doc--missing" in modal.text
    finally:
        with contextlib.suppress(FileNotFoundError):
            caminho.unlink()


def test_ui_compras_upload_comprovante_invalido_rejeita_lote(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _login_admin(client)
    compra_id = _seed_compra(client, "45678912322")
    monkeypatch.setattr(compras_ui, "uploads_compra_dir", lambda _id: tmp_path)

    resp = client.post(
        f"/ui/compras/{compra_id}/comprovantes",
        files={"comprovantes": ("malicioso.gif", b"dados", "image/gif")},
    )

    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_ui_dashboard_filtra_por_mes(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    hoje = datetime.now(UTC).date()

    cliente_resp = client.post(
        "/clientes",
        json={
            "nome": "Cliente Dashboard",
            "documento": "12312312399",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert cliente_resp.status_code == 201

    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    venda_resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_resp.json()["id"],
            "veiculo_id": veiculo_id,
            "data_venda": hoje.isoformat(),
            "valor_venda": "85000.00",
            "valor_entrada": "10000.00",
            "forma_pagamento": "financiamento",
            "parcelas": 36,
            "status": "aprovado",
        },
        headers=headers,
    )
    assert venda_resp.status_code == 201

    pagina_padrao = client.get("/ui/dashboard")
    mes_atual = f"{hoje.year:04d}-{hoje.month:02d}"

    assert pagina_padrao.status_code == 200
    assert f'value="{mes_atual}" selected="selected"' in pagina_padrao.text

    pagina = client.get(f"/ui/dashboard?mes={mes_atual}")

    assert pagina.status_code == 200
    assert f'value="{mes_atual}" selected="selected"' in pagina.text
    assert "30 dias" not in pagina.text
    assert "90 dias" not in pagina.text
    assert "12 meses" not in pagina.text
    assert 'id="dashboard-mes"' in pagina.text
    assert "Mês" in pagina.text
    assert "Tendência de vendas por semana" not in pagina.text
    assert "Funil de vendas" not in pagina.text
    assert "R$ 85.000" in pagina.text


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


def test_ui_admin_crud_custos_veiculos_e_csv(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    pagina = client.get("/ui/custos-veiculos")
    assert pagina.status_code == 200
    assert "Total de custos" in pagina.text
    assert "Novo custo" in pagina.text

    criado = client.post(
        "/ui/custos-veiculos",
        data={
            "veiculo_id": str(veiculo_id),
            "categoria": "Manutenção",
            "data_custo": "2026-07-14",
            "valor": "250.00",
            "descricao": "Troca de óleo",
        },
    )
    assert criado.status_code == 200
    assert "Manutenção" in criado.text
    assert "R$ 250,00" in criado.text

    pagina = client.get("/ui/custos-veiculos")
    assert "R$ 250,00" in pagina.text
    assert "1" in pagina.text

    exportado = client.get("/ui/custos-veiculos/exportar")
    assert exportado.status_code == 200
    assert (
        exportado.headers["content-disposition"]
        == 'attachment; filename="custos_veiculos.csv"'
    )
    assert "Manutenção" in exportado.text

    match = re.search(r"/ui/custos-veiculos/(\d+)/editar", pagina.text)
    assert match is not None
    custo_id = match.group(1)

    editado = client.post(
        f"/ui/custos-veiculos/{custo_id}",
        data={
            "veiculo_id": str(veiculo_id),
            "categoria": "Peças",
            "data_custo": "2026-07-15",
            "valor": "300.00",
            "descricao": "",
        },
    )
    assert editado.status_code == 200
    assert "Peças" in editado.text
    assert "R$ 300,00" in editado.text

    excluido = client.post(f"/ui/custos-veiculos/{custo_id}/excluir")
    assert excluido.status_code == 200
    assert "Nenhum custo encontrado" in excluido.text


def test_ui_detalhe_veiculo_busca_custos_do_veiculo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    chamados: list[int] = []

    def fake_list_by_veiculo(_session: Session, item_id: int) -> list[Any]:
        chamados.append(item_id)
        return []

    def fail_list_all(*_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("vehicle detail must not load every custo_veiculo row")

    monkeypatch.setattr(custo_veiculo, "list_by_veiculo", fake_list_by_veiculo)
    monkeypatch.setattr(custo_veiculo, "list_all", fail_list_all)

    resp = client.get(f"/ui/veiculos/{veiculo_id}/detalhes")

    assert resp.status_code == 200
    assert chamados == [veiculo_id]


def test_ui_custos_veiculos_respeita_permissao_de_perfil(
    client: TestClient,
) -> None:
    _login_admin(client)
    client.post(
        "/ui/perfis",
        data={"nome": "Custos", "paginas": "custos-veiculos"},
    )
    client.post(
        "/ui/usuarios",
        data={
            "username": "custos_user",
            "senha": "abc",
            "papel": "funcionario",
            "perfil_id": "1",
        },
    )
    client.post("/ui/login", data={"username": "custos_user", "password": "abc"})

    permitido = client.get("/ui/custos-veiculos")
    assert permitido.status_code == 200
    assert "Custos de veículos" in permitido.text

    bloqueado = client.get("/ui/veiculos")
    assert bloqueado.status_code == 403


def test_ui_veiculos_respeita_permissao_de_perfil_de_debitos(
    client: TestClient,
) -> None:
    _login_admin(client)
    client.post(
        "/ui/perfis",
        data={
            "nome": "Veiculos",
            "paginas": "veiculos",
            "oculto__veiculos__debitos": "on",
        },
    )
    client.post(
        "/ui/usuarios",
        data={
            "username": "veiculos_user",
            "senha": "abc",
            "papel": "funcionario",
            "perfil_id": "1",
        },
    )
    client.post("/ui/login", data={"username": "veiculos_user", "password": "abc"})

    permitido = client.get("/ui/veiculos")
    assert permitido.status_code == 200
    assert "Valor disponível" not in permitido.text
    assert 'data-col-label="Débitos"' not in permitido.text


def test_ui_exportacao_respeita_permissao_de_campo(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/perfis",
        data={
            "nome": "Sem Preco",
            "paginas": "veiculos",
            "oculto__veiculos__preco": "on",
        },
    )
    client.post(
        "/ui/usuarios",
        data={
            "username": "sem_preco",
            "senha": "abc",
            "papel": "funcionario",
            "perfil_id": "1",
        },
    )
    client.post("/ui/login", data={"username": "sem_preco", "password": "abc"})

    resp = client.get("/ui/veiculos/exportar")

    assert resp.status_code == 200
    assert "Preco" not in resp.text
    assert "85000.00" not in resp.text


def test_ui_clientes_modal_cadastro_cria_cliente(client: TestClient) -> None:
    _login_admin(client)

    novo = client.get("/ui/clientes/todos/novo")
    assert novo.status_code == 200
    assert 'data-testid="cliente-form-name"' in novo.text

    criado = client.post(
        "/ui/clientes/todos",
        data={
            "nome": "Cliente Modal Teste",
            "documento": "12345678905",
            "tipo": "pessoa_fisica",
            "email": "cliente.modal@example.com",
            "telefone": "11988887777",
        },
    )

    assert criado.status_code == 200
    assert "Cliente Modal Teste" in criado.text


def test_ui_clientes_modal_cadastro_preserva_erro_de_validacao(
    client: TestClient,
) -> None:
    _login_admin(client)

    resp = client.post(
        "/ui/clientes/todos",
        data={
            "nome": "Cliente Documento Invalido",
            "documento": "abc",
            "tipo": "pessoa_fisica",
        },
    )

    assert resp.status_code == 400
    assert 'data-testid="cliente-form-name"' in resp.text
    assert "Cliente Documento Invalido" not in client.get("/ui/clientes/todos").text


def _login_admin(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})


def test_ui_conta_admin_exibe_pagina(client: TestClient) -> None:
    _login_admin(client)

    resp = client.get("/ui/conta")

    assert resp.status_code == 200
    assert "Minha conta" in resp.text
    assert "admin" in resp.text


def test_ui_conta_funcionario_exibe_pagina(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "conta_user", "senha": "abc", "papel": "funcionario"},
    )
    client.post("/ui/login", data={"username": "conta_user", "password": "abc"})

    resp = client.get("/ui/conta")

    assert resp.status_code == 200
    assert "Minha conta" in resp.text
    assert "conta_user" in resp.text


def test_ui_usuario_criar_rejeita_perfil_inexistente(client: TestClient) -> None:
    _login_admin(client)

    resp = client.post(
        "/ui/usuarios",
        data={
            "username": "perfil_invalido",
            "senha": "abc",
            "papel": "funcionario",
            "perfil_id": "999",
        },
    )

    assert resp.status_code == 400
    assert "perfil não encontrado" in resp.text


def test_ui_usuario_editar_rejeita_perfil_inexistente(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "perfil_valido", "senha": "abc", "papel": "funcionario"},
    )
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    usuarios_resp = client.get(
        "/usuarios", headers={"Authorization": f"Bearer {token}"}
    )
    usuario_id = next(
        item["id"]
        for item in usuarios_resp.json()
        if item["username"] == "perfil_valido"
    )

    resp = client.post(
        f"/ui/usuarios/{usuario_id}/editar",
        data={
            "username": "perfil_valido",
            "papel": "funcionario",
            "ativo": "on",
            "perfil_id": "999",
        },
    )

    assert resp.status_code == 400
    assert "perfil não encontrado" in resp.text


def test_ui_user_funcionario_sem_perfil_pode_acessar_conta(
    db_session: Session,
) -> None:
    user = usuario.create(
        db_session,
        usuario.UsuarioCreate(
            username="conta_sem_perfil", senha="abc", papel=usuario.Papel.funcionario
        ),
    )
    token = auth.create_access_token(user.username)

    autenticado = get_ui_user(_request("/ui/conta"), db_session, token)

    assert autenticado.id == user.id


def test_ui_user_funcionario_sem_perfil_nao_acessa_pagina_ui_desconhecida(
    db_session: Session,
) -> None:
    user = usuario.create(
        db_session,
        usuario.UsuarioCreate(
            username="nova_pagina", senha="abc", papel=usuario.Papel.funcionario
        ),
    )
    token = auth.create_access_token(user.username)

    with pytest.raises(NaoAutorizadoError):
        get_ui_user(_request("/ui/nova-pagina"), db_session, token)


def test_ui_user_funcionario_sem_perfil_nao_usa_prefixo_conta_como_excecao(
    db_session: Session,
) -> None:
    user = usuario.create(
        db_session,
        usuario.UsuarioCreate(
            username="contabilidade", senha="abc", papel=usuario.Papel.funcionario
        ),
    )
    token = auth.create_access_token(user.username)

    with pytest.raises(NaoAutorizadoError):
        get_ui_user(_request("/ui/contabilidade"), db_session, token)


def test_ui_conta_troca_propria_senha(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "senha_user", "senha": "abc", "papel": "funcionario"},
    )
    client.post("/ui/login", data={"username": "senha_user", "password": "abc"})

    resp = client.post(
        "/ui/conta/senha",
        data={
            "senha_atual": "abc",
            "nova_senha": "nova123",
            "confirmar_senha": "nova123",
        },
    )

    assert resp.status_code == 200
    assert "Senha alterada com sucesso." in resp.text
    assert 'class="alert alert--success"' in resp.text

    login = client.post(
        "/ui/login",
        data={"username": "senha_user", "password": "nova123"},
        follow_redirects=False,
    )
    assert login.status_code == 303


def test_ui_conta_rejeita_senha_atual_invalida(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "senha_invalida", "senha": "abc", "papel": "funcionario"},
    )
    client.post("/ui/login", data={"username": "senha_invalida", "password": "abc"})

    resp = client.post(
        "/ui/conta/senha",
        data={
            "senha_atual": "errada",
            "nova_senha": "nova123",
            "confirmar_senha": "nova123",
        },
    )

    assert resp.status_code == 400
    assert "Senha atual incorreta" in resp.text

    login = client.post(
        "/ui/login",
        data={"username": "senha_invalida", "password": "abc"},
        follow_redirects=False,
    )
    assert login.status_code == 303


def test_ui_conta_rejeita_confirmacao_diferente(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "senha_conf", "senha": "abc", "papel": "funcionario"},
    )
    client.post("/ui/login", data={"username": "senha_conf", "password": "abc"})

    resp = client.post(
        "/ui/conta/senha",
        data={
            "senha_atual": "abc",
            "nova_senha": "nova123",
            "confirmar_senha": "outra123",
        },
    )

    assert resp.status_code == 400
    assert "A confirmação não coincide com a nova senha" in resp.text


def test_ui_admin_exclui_outro_usuario(client: TestClient) -> None:
    """Admin pode excluir outro usuário pela UI."""
    _login_admin(client)
    # cria um vendedor pela UI
    client.post(
        "/ui/usuarios",
        data={"username": "vendedor_ui", "senha": "abc", "papel": "funcionario"},
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


def test_ui_admin_autoexclusao_htmx_retorna_apenas_linhas(client: TestClient) -> None:
    """Erro de autoexclusão não deve substituir o alvo HTMX pela página inteira."""
    _login_admin(client)
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    usuarios = client.get(
        "/usuarios", headers={"Authorization": f"Bearer {token}"}
    ).json()
    admin_id = next(u["id"] for u in usuarios if u["username"] == "admin")

    resp = client.post(
        f"/ui/usuarios/{admin_id}/excluir",
        headers={"HX-Request": "true"},
    )

    assert resp.status_code == 400
    assert '<tbody id="linhas"' in resp.text
    assert "não pode excluir a si mesmo" in resp.text.lower()
    assert "<html" not in resp.text.lower()


def test_ui_admin_troca_senha_de_outro(client: TestClient) -> None:
    """Admin pode trocar a senha de outro usuário pela UI."""
    _login_admin(client)
    # cria vendedor pela UI
    client.post(
        "/ui/usuarios",
        data={"username": "ui_vendedor", "senha": "abc", "papel": "funcionario"},
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


def test_ui_admin_rejeita_perfil_inexistente_ao_alterar_usuario(
    client: TestClient,
) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "perfil_invalido", "senha": "abc", "papel": "funcionario"},
    )
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    usuario_id = next(u["id"] for u in usuarios if u["username"] == "perfil_invalido")

    resp = client.post(
        f"/ui/usuarios/{usuario_id}/perfil",
        data={"perfil_id": "999999"},
    )

    assert resp.status_code == 400
    assert "Perfil inválido" in resp.text


def test_ui_admin_edita_usuario_e_troca_senha_no_modal(client: TestClient) -> None:
    """O modal de edição permite atualizar dados e redefinir a senha."""
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "editar_ui", "senha": "abc", "papel": "funcionario"},
    )
    token_resp = client.post("/login", data={"username": "admin", "password": "senha"})
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    usuarios = client.get("/usuarios", headers=headers).json()
    usuario_id = next(u["id"] for u in usuarios if u["username"] == "editar_ui")

    pagina = client.get("/ui/usuarios")
    assert f"/ui/usuarios/{usuario_id}/senha" not in pagina.text

    resp = client.get(f"/ui/usuarios/{usuario_id}/editar")
    assert resp.status_code == 200
    assert 'name="senha"' in resp.text

    resp = client.post(
        f"/ui/usuarios/{usuario_id}/editar",
        data={
            "username": "editar_ui",
            "senha": "nova_editada",
            "papel": "funcionario",
            "ativo": "true",
        },
    )
    assert resp.status_code == 200

    assert (
        client.post(
            "/ui/login",
            data={"username": "editar_ui", "password": "nova_editada"},
            follow_redirects=False,
        ).status_code
        == 303
    )


def test_ui_conta_exibe_perfil_do_usuario_logado(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/conta")
    assert resp.status_code == 200
    assert "admin" in resp.text


def test_ui_conta_troca_a_propria_senha(client: TestClient) -> None:
    _login_admin(client)
    resp = client.post(
        "/ui/conta/senha",
        data={
            "senha_atual": "senha",
            "nova_senha": "nova_senha_admin",
            "confirmar_senha": "nova_senha_admin",
        },
    )
    assert resp.status_code == 200

    resp = client.post(
        "/ui/login",
        data={"username": "admin", "password": "nova_senha_admin"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_ui_conta_rejeita_senha_atual_incorreta(client: TestClient) -> None:
    _login_admin(client)
    resp = client.post(
        "/ui/conta/senha",
        data={
            "senha_atual": "errada",
            "nova_senha": "qualquer",
            "confirmar_senha": "qualquer",
        },
    )
    assert resp.status_code == 400
    assert "senha atual incorreta" in resp.text.lower()


def test_ui_conta_rejeita_confirmacao_divergente(client: TestClient) -> None:
    _login_admin(client)
    resp = client.post(
        "/ui/conta/senha",
        data={
            "senha_atual": "senha",
            "nova_senha": "abc123",
            "confirmar_senha": "outra",
        },
    )
    assert resp.status_code == 400
    assert "não coincide" in resp.text.lower()


def _admin_headers(client: TestClient) -> dict[str, str]:
    token = client.post(
        "/login", data={"username": "admin", "password": "senha"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@contextlib.contextmanager
def _client_with_failing_final_commit() -> Iterator[
    tuple[TestClient, Session, dict[str, bool]]
]:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
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
        fail_commit = {"enabled": False}

        def _raise_commit_error() -> None:
            raise IntegrityError("", {}, Exception("commit falhou"))

        def override() -> Iterator[Session]:
            try:
                yield session
                if fail_commit["enabled"]:
                    _raise_commit_error()
                session.commit()
                invoke_post_commit(session)
            except Exception:
                session.rollback()
                raise

        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app, raise_server_exceptions=False) as test_client:
                yield test_client, session, fail_commit
        finally:
            app.dependency_overrides.clear()
    engine.dispose()


@contextlib.contextmanager
def _client_with_contract_write_failure() -> Iterator[tuple[TestClient, Session]]:
    engine = create_test_engine()
    with Session(engine) as session:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        session.add(u)
        session.flush()
        session.info["usuario_id"] = u.id
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
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app, raise_server_exceptions=False) as test_client:
                yield test_client, session
        finally:
            app.dependency_overrides.clear()
    engine.dispose()


def _criar_cliente(
    client: TestClient, headers: dict[str, str], nome: str, documento: str
) -> int:
    resp = client.post(
        "/clientes",
        json={
            "nome": nome,
            "documento": documento,
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return int(resp.json()["id"])


def _classes_do_botao(html: str, element_id: str) -> str:
    match = re.search(rf'id="{re.escape(element_id)}" class="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _remover_uploads_renderizados(html: str) -> None:
    for url in re.findall(r"/static/uploads/[^\"<]+", html):
        with contextlib.suppress(FileNotFoundError):
            Path("bases/xtreme_system/api").joinpath(url.lstrip("/")).unlink()


def _seed_compra(client: TestClient, documento: str) -> int:
    headers = _admin_headers(client)
    cliente_resp = client.post(
        "/clientes",
        json={
            "nome": f"Cliente Compra {documento[-2:]}",
            "documento": documento,
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    assert cliente_resp.status_code == 201
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    compra_resp = client.post(
        "/compras",
        json={
            "cliente_id": cliente_resp.json()["id"],
            "veiculo_id": veiculo_id,
            "data_compra": "2026-07-09",
            "valor_compra": "84000.00",
        },
        headers=headers,
    )
    assert compra_resp.status_code == 201
    return int(compra_resp.json()["id"])


def test_ui_vendas_nao_grava_contrato_se_commit_final_falhar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.vendas.uploads_contrato_venda_dir",
        lambda _id: tmp_path,
    )

    with _client_with_failing_final_commit() as (client, session, fail_commit):
        _login_admin(client)
        headers = _admin_headers(client)
        cliente_id = _criar_cliente(client, headers, "Carlos Lima", "98765432100")
        veiculo_id = veiculo.list_all(session)[0].id

        fail_commit["enabled"] = True
        resp = client.post(
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
            },
        )

        assert venda.list_all(session) == []

    assert resp.status_code == 200
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_ui_vendas_aborta_se_gravacao_do_contrato_falhar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "xtreme_system.api.routes.ui_routes.vendas.uploads_contrato_venda_dir",
        lambda _id: tmp_path,
    )

    def fail_write_bytes(_self: Path, _data: bytes) -> int:
        raise OSError("disco cheio")

    monkeypatch.setattr(Path, "write_bytes", fail_write_bytes)

    with _client_with_contract_write_failure() as (client, session):
        _login_admin(client)
        headers = _admin_headers(client)
        cliente_id = _criar_cliente(client, headers, "Carlos Lima", "98765432100")
        veiculo_id = veiculo.list_all(session)[0].id

        resp = client.post(
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
            },
        )

        assert resp.status_code == 500
        assert venda.list_all(session) == []
        assert documento_contrato_venda.list_all(session) == []


def test_ui_compras_nao_grava_comprovante_se_commit_final_falhar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(compras_ui, "uploads_compra_dir", lambda _id: tmp_path)

    with _client_with_failing_final_commit() as (client, session, fail_commit):
        _login_admin(client)
        headers = _admin_headers(client)
        investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]
        veiculo_resp = client.post(
            "/veiculos",
            json={
                "tipo": "carro",
                "tipo_entrada": "compra",
                "placa": "CMP1A23",
                "modelo": "Corolla",
                "cor": "Preto",
                "ano": 2022,
                "km": 30000,
                "preco": "84000.00",
                "investidor_id": investidor_id,
            },
            headers=headers,
        )
        assert veiculo_resp.status_code == 201
        cliente_id = _criar_cliente(client, headers, "Carlos Compra", "45678912300")

        fail_commit["enabled"] = True
        resp = client.post(
            "/ui/compras",
            data={
                "cliente_id": str(cliente_id),
                "veiculo_id": str(veiculo_resp.json()["id"]),
                "data_compra": "2026-07-09",
                "valor_compra": "84000.00",
            },
            files={
                "comprovantes_pagamento": (
                    "comprovante.pdf",
                    b"%PDF-conteudo-pagto",
                    "application/pdf",
                )
            },
        )

        assert compra.list_all(session) == []

    assert resp.status_code == 200
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_veiculo_criado_via_api_gera_lancamento_visivel_no_caixa(
    client: TestClient,
) -> None:
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Carla"}, headers=headers).json()
    v = client.post(
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
    ).json()
    cli = client.post(
        "/clientes",
        json={
            "nome": "Vendedor Carla",
            "documento": "11122233344",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    ).json()
    client.post(
        "/compras",
        json={
            "cliente_id": cli["id"],
            "veiculo_id": v["id"],
            "data_compra": "2026-07-01",
            "valor_compra": "18000.00",
        },
        headers=headers,
    )

    _login_admin(client)
    pagina = client.get(f"/ui/investidores/{inv['id']}/lancamentos")
    assert pagina.status_code == 200
    assert "HB20" in pagina.text
    # o lançamento de custo reflete o valor da compra, não o preço anunciado
    assert "18.000,00" in pagina.text
    assert "20.000,00" not in pagina.text


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


def test_ui_lancamentos_crud_manual(client: TestClient) -> None:
    headers = _admin_headers(client)
    investidor_id = client.get("/investidores", headers=headers).json()[0]["id"]

    _login_admin(client)
    novo = client.get(f"/ui/investidores/{investidor_id}/lancamentos/novo")
    assert novo.status_code == 200
    assert "Novo lançamento" in novo.text

    criado = client.post(
        f"/ui/investidores/{investidor_id}/lancamentos",
        data={
            "tipo": "aporte",
            "valor": "1000.00",
            "descricao": "Aporte manual",
        },
    )
    assert criado.status_code == 200
    lancamentos = client.get("/lancamentos-caixa", headers=headers).json()
    manual = next(
        item
        for item in lancamentos
        if item["investidor_id"] == investidor_id
        and item["origem"] == "manual"
        and item["descricao"] == "Aporte manual"
    )

    editar = client.get(
        f"/ui/investidores/{investidor_id}/lancamentos/{manual['id']}/editar"
    )
    assert editar.status_code == 200
    assert "Editar lançamento" in editar.text

    atualizado = client.post(
        f"/ui/investidores/{investidor_id}/lancamentos/{manual['id']}",
        data={
            "tipo": "aporte",
            "valor": "1250.00",
            "descricao": "Aporte atualizado",
        },
    )
    assert atualizado.status_code == 200
    atualizado_item = next(
        item
        for item in client.get("/lancamentos-caixa", headers=headers).json()
        if item["id"] == manual["id"]
    )
    assert atualizado_item["valor"] == "1250.00"
    assert atualizado_item["descricao"] == "Aporte atualizado"

    excluido = client.post(
        f"/ui/investidores/{investidor_id}/lancamentos/{manual['id']}/excluir"
    )
    assert excluido.status_code == 200
    assert all(
        item["id"] != manual["id"]
        for item in client.get("/lancamentos-caixa", headers=headers).json()
    )


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


@pytest.mark.parametrize(
    ("method", "suffix", "data"),
    [
        ("get", "/editar", None),
        ("post", "", {"valor": "1.00"}),
        ("post", "/excluir", None),
    ],
)
def test_lancamento_automatico_nao_pode_ser_alterado_via_ui(
    client: TestClient, method: str, suffix: str, data: dict[str, str] | None
) -> None:
    headers = _admin_headers(client)
    inv = client.post("/investidores", json={"nome": "Dora UI"}, headers=headers).json()
    v = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Kwid UI",
            "cor": "Branco",
            "ano": 2023,
            "placa": "YYY8Y89",
            "km": 500,
            "preco": "18000.00",
            "investidor_id": inv["id"],
        },
        headers=headers,
    ).json()
    cliente_id = _criar_cliente(client, headers, "Comprador Dora UI", "32132132155")
    compra_resp = client.post(
        "/compras",
        json={
            "cliente_id": cliente_id,
            "veiculo_id": v["id"],
            "data_compra": "2026-07-09",
            "valor_compra": "17000.00",
        },
        headers=headers,
    )
    assert compra_resp.status_code == 201
    lancamentos = client.get("/lancamentos-caixa", headers=headers).json()
    automatico = next(item for item in lancamentos if item["veiculo_id"] == v["id"])

    _login_admin(client)
    path = (
        f"/ui/investidores/{automatico['investidor_id']}"
        f"/lancamentos/{automatico['id']}{suffix}"
    )
    resp = client.get(path) if method == "get" else client.post(path, data=data)
    assert resp.status_code == 400
    assert "Lançamento automático não pode ser alterado manualmente" in resp.text
    assert any(
        item["id"] == automatico["id"]
        for item in client.get("/lancamentos-caixa", headers=headers).json()
    )


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

    cli = client.post(
        "/clientes",
        json={
            "nome": "Vendedor Eva",
            "documento": "55566677788",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    ).json()
    compra_resp = client.post(
        "/compras",
        json={
            "cliente_id": cli["id"],
            "veiculo_id": v["id"],
            "data_compra": "2026-07-01",
            "valor_compra": "13000.00",
        },
        headers=headers,
    )
    assert compra_resp.status_code == 201, compra_resp.text

    resp = client.patch(
        f"/veiculos/{v['id']}",
        json={"preco": "17000.00", "investidor_id": outro["id"]},
        headers=headers,
    )
    assert resp.status_code == 200

    lancamentos = client.get("/lancamentos-caixa", headers=headers).json()
    lanc = next(item for item in lancamentos if item["veiculo_id"] == v["id"])
    # editar o preço anunciado não mexe no custo; o investidor, sim
    assert lanc["valor"] == "13000.00"
    assert lanc["investidor_id"] == outro["id"]

    # já editar o valor da compra reflete no lançamento de custo
    patch_compra = client.patch(
        f"/compras/{compra_resp.json()['id']}",
        json={"valor_compra": "14500.00"},
        headers=headers,
    )
    assert patch_compra.status_code == 200, patch_compra.text
    lancamentos = client.get("/lancamentos-caixa", headers=headers).json()
    lanc = next(item for item in lancamentos if item["veiculo_id"] == v["id"])
    assert lanc["valor"] == "14500.00"


def test_ui_dashboard_mostra_kpis(client: TestClient) -> None:
    """Dashboard admin mostra KPIs de vendas e estoque."""
    _login_admin(client)

    # sem vendas, deve retornar 200 com dados zerados
    resp = client.get("/ui/dashboard")
    assert resp.status_code == 200
    assert "Dashboard" in resp.text
    assert "Vendas" in resp.text
    assert "Total de veículos" in resp.text
    assert 'class="sidebar__user-link nav__link' in resp.text
    assert resp.text.count('href="/ui/conta"') == 1
    assert "Taxa de conversão" not in resp.text
    assert "Tendência de vendas por semana" not in resp.text
    assert "Funil de vendas" not in resp.text

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
    assert "Atividades Recentes" in resp.text
    assert "Venda #" in resp.text


def test_ui_dashboard_resumo_ticket_vendas_mes_usa_query_unica(
    db_session: Session,
) -> None:
    inv = investidor.create(
        db_session, investidor.InvestidorCreate(nome="Investidor B")
    )
    cli = cliente.create(
        db_session,
        cliente.ClienteCreate(
            nome="Cliente Dashboard Query",
            documento="98765432100",
            tipo=cliente.TipoCliente.pessoa_fisica,
        ),
    )
    vei = veiculo.create(
        db_session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Corolla",
            cor="Prata",
            ano=2024,
            placa="QRY1A23",
            km=1000,
            preco=Decimal("100000.00"),
            investidor_id=inv.id,
        ),
    )
    venda.create(
        db_session,
        venda.VendaCreate(
            cliente_id=cli.id,
            veiculo_id=vei.id,
            data_venda=date(2026, 7, 10),
            valor_venda=Decimal("90000.00"),
            forma_pagamento="financiamento",
            parcelas=48,
        ),
    )
    db_session.flush()
    engine = db_session.get_bind()
    assert isinstance(engine, Engine)
    selects = 0

    def count_venda_selects(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        nonlocal selects
        normalized = statement.lstrip().upper()
        if normalized.startswith("SELECT") and "venda" in statement:
            selects += 1

    event.listen(engine, "before_cursor_execute", count_venda_selects)
    try:
        count, total, ticket_medio = dashboard_ui._resumo_ticket_vendas_mes(  # noqa: SLF001
            db_session, date(2026, 7, 1)
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_venda_selects)

    assert selects == 1
    assert count == 1
    assert total == Decimal("90000.00")
    assert ticket_medio == Decimal("90000.00")


# ---- Validação de uploads ----


_MAGIC: dict[str, bytes] = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a",
    ".webp": b"RIFF",
    ".pdf": b"%PDF",
}


class _FakeFile:
    """Minimal file-like stub with seek/tell for size fallback in tests."""

    def __init__(self, size: int, filename: str = ""):
        self._size = size
        self._pos = 0
        self._filename = filename

    def seek(self, offset: int, whence: int = 0) -> int:
        self._pos = self._size + offset if whence == 2 else offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, _n: int = -1) -> bytes:
        return self._magic() or b""

    def _magic(self) -> bytes | None:
        ext = Path(self._filename).suffix.lower()
        return _MAGIC.get(ext)


class _FakeUpload:
    """Minimal UploadFile-like stub for unit tests (no network, no spooled file)."""

    def __init__(self, filename: str, content_type: str | None, size: int | None):
        self.filename = filename
        self.content_type = content_type
        self._size = size
        self.file = _FakeFile(size or 0, filename=filename)

    @property
    def size(self) -> int | None:
        return self._size


def test_validar_uploads_extensao_invalida() -> None:
    arq = _FakeUpload("malicioso.gif", "image/gif", 100)
    msg = validar_uploads([arq])  # type: ignore[list-item]
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
        assert validar_uploads([arq]) is None, f"{nome} deveria passar"  # type: ignore[list-item]


def test_validar_uploads_content_type_divergente() -> None:
    arq = _FakeUpload("foto.jpg", "application/pdf", 1000)
    msg = validar_uploads([arq])  # type: ignore[list-item]
    assert msg is not None
    assert "Conteúdo não corresponde" in msg


def test_validar_uploads_content_type_ausente_passa() -> None:
    arq = _FakeUpload("foto.jpg", None, 1000)
    assert validar_uploads([arq]) is None  # type: ignore[list-item]


def test_validar_uploads_arquivo_maior_que_5mb() -> None:
    arq = _FakeUpload("grande.jpg", "image/jpeg", 5 * 1024 * 1024 + 1)
    msg = validar_uploads([arq])  # type: ignore[list-item]
    assert msg is not None
    assert "excede 5 MB" in msg


def test_validar_uploads_lote_rejeitado_se_um_falha() -> None:
    bons = _FakeUpload("ok.jpg", "image/jpeg", 1000)
    mau = _FakeUpload("mau.exe", "application/octet-stream", 1000)
    msg = validar_uploads([bons, mau])  # type: ignore[list-item]
    assert msg is not None
    assert "Tipo não permitido" in msg


def test_validar_uploads_sem_filename_ignorado() -> None:
    arq = _FakeUpload("", None, None)
    assert validar_uploads([arq]) is None  # type: ignore[list-item]


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
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]
    monkeypatch.setattr(veiculos_imagens_ui, "uploads_dir", lambda _id: tmp_path)

    resp = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("malicioso.gif", b"dados", "image/gif")},
    )
    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    assert ".gif" in resp.text
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_upload_imagem_veiculo_remove_arquivo_se_create_falha(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    veiculo_id = client.get("/veiculos", headers=headers).json()[0]["id"]

    def falha_create(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db indisponivel")

    monkeypatch.setattr(veiculos_imagens_ui, "uploads_dir", lambda _id: tmp_path)
    monkeypatch.setattr(imagem_veiculo, "create", falha_create)

    resp = client.post(
        f"/ui/veiculos/{veiculo_id}/imagens",
        files={"imagens": ("foto.jpg", b"\xff\xd8\xffdados", "image/jpeg")},
    )

    assert resp.status_code == 500

    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_salvar_documentos_cliente_remove_arquivo_se_create_falha(
    tmp_path: Path,
) -> None:
    def falha_create(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db indisponivel")

    with pytest.raises(RuntimeError, match="db indisponivel"):
        salvar_arquivos(
            cast(Session, _FakeSession()),
            upload_dir=tmp_path,
            url_prefix="/static/uploads/clientes/1/documentos",
            create_fn=cast(Callable[[Session, Any], Any], falha_create),
            schema=imagem_documento_cliente.ImagemDocumentoClienteCreate,
            fk_field="cliente_id",
            fk_id=1,
            arquivos=[_FakeUpload("doc.pdf", "application/pdf", 10)],  # type: ignore[list-item]
        )

    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_salvar_documento_veiculo_remove_arquivo_se_create_falha(
    tmp_path: Path,
) -> None:
    def falha_create(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db indisponivel")

    with pytest.raises(RuntimeError, match="db indisponivel"):
        salvar_arquivos(
            cast(Session, _FakeSession()),
            upload_dir=tmp_path,
            url_prefix="/static/uploads/veiculos/1/documentos",
            create_fn=cast(Callable[[Session, Any], Any], falha_create),
            schema=documento_veiculo.DocumentoVeiculoCreate,
            fk_field="veiculo_id",
            fk_id=1,
            arquivos=[_FakeUpload("doc.pdf", "application/pdf", 10)],  # type: ignore[list-item]
        )

    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_upload_documento_cliente_extensao_invalida_rejeitada(
    client: TestClient,
) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    cliente_id = client.post(
        "/clientes",
        json={"nome": "X", "documento": "11122233344", "tipo": "pessoa_fisica"},
        headers=headers,
    ).json()["id"]

    resp = client.post(
        f"/ui/clientes/{cliente_id}/documentos",
        files=[("documentos", ("notas.txt", b"texto", "text/plain"))],
    )
    assert resp.status_code == 400
    assert "Tipo não permitido" in resp.text
    assert ".txt" in resp.text


# ---- Auditoria (UI + JSON) ----


def test_ui_auditoria_sem_cookie_redireciona_login() -> None:
    with TestClient(app) as client:
        resp = client.get("/ui/auditoria", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/ui/login"


def test_ui_auditoria_admin_ve_lista(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria")
    assert resp.status_code == 200
    assert "Auditoria" in resp.text
    assert 'id="auditoria-resultado"' in resp.text
    # barreira de filtros presente
    assert "Filtrar" in resp.text


def test_ui_auditoria_filtros_htmx_retorna_parcial(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert 'id="auditoria-resultado"' in resp.text
    assert "Auditoria" not in resp.text  # parcial não traz o título da página


def test_ui_auditoria_vendedor_recebe_403(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "vend_audit", "senha": "abc", "papel": "funcionario"},
    )
    client.post("/ui/login", data={"username": "vend_audit", "password": "abc"})
    resp = client.get("/ui/auditoria")
    assert resp.status_code == 403
    assert "admin" in resp.text.lower()


def test_ui_auditoria_limit_acima_do_teto_retorna_422(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria?limit=100000")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "limit"]


def test_ui_auditoria_offset_negativo_retorna_422(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria?offset=-1")
    assert resp.status_code == 422


def test_ui_auditoria_tipo_acao_invalido_retorna_422(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria?tipo_acao=DROP")
    assert resp.status_code == 422


def test_ui_auditoria_filtros_vazios_sao_ignorados(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria?tipo_acao=&usuario_id=&tabela=&data_de=")
    assert resp.status_code == 200


def test_ui_auditoria_periodo_invertido_retorna_422(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria?data_de=2026-12-31&data_ate=2026-01-01")
    assert resp.status_code == 422


def test_ui_auditoria_exportar_csv(client: TestClient) -> None:
    _login_admin(client)
    resp = client.get("/ui/auditoria/exportar")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == 'attachment; filename="auditoria.csv"'
    assert "text/csv" in resp.headers["content-type"]


def test_ui_auditoria_detalhe_modal(client: TestClient) -> None:
    _login_admin(client)
    headers = _admin_headers(client)
    rows = client.get("/auditoria", headers=headers).json()
    assert rows
    reg_id = rows[0]["id"]
    resp = client.get(f"/ui/auditoria/{reg_id}/detalhe")
    assert resp.status_code == 200
    assert "Antes" in resp.text
    assert "Depois" in resp.text


def test_api_auditoria_admin_lista_e_filtra(client: TestClient) -> None:
    headers = _admin_headers(client)
    resp = client.get("/auditoria", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert rows
    tabelas = {r["tabela"] for r in rows}
    alguma = next(iter(tabelas))
    filtrado = client.get(
        "/auditoria", params={"tabela": alguma}, headers=headers
    ).json()
    assert filtrado
    assert all(r["tabela"] == alguma for r in filtrado)


def test_api_auditoria_vendedor_forbidden(client: TestClient) -> None:
    _login_admin(client)
    client.post(
        "/ui/usuarios",
        data={"username": "vend_api", "senha": "abc", "papel": "funcionario"},
    )
    token = client.post(
        "/login", data={"username": "vend_api", "password": "abc"}
    ).json()["access_token"]
    resp = client.get("/auditoria", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_ui_usuario_management_atribui_admin_na_auditoria(
    client: TestClient,
) -> None:
    """Create/trocar-senha/perfil/delete de usuário pela UI devem atribuir o admin
    como autor nas linhas de auditoria (não None)."""
    _login_admin(client)
    headers = _admin_headers(client)
    admin_id = next(
        u["id"]
        for u in client.get("/usuarios", headers=headers).json()
        if u["username"] == "admin"
    )

    # CREATE via UI
    resp = client.post(
        "/ui/usuarios",
        data={"username": "alvo_ui", "senha": "abc", "papel": "funcionario"},
    )
    assert resp.status_code == 200
    alvo_id = next(
        u["id"]
        for u in client.get("/usuarios", headers=headers).json()
        if u["username"] == "alvo_ui"
    )

    # UPDATE senha via UI
    assert (
        client.post(
            f"/ui/usuarios/{alvo_id}/senha", data={"nova_senha": "nova"}
        ).status_code
        == 200
    )

    # UPDATE perfil via UI (perfil_id=None)
    assert client.post(f"/ui/usuarios/{alvo_id}/perfil", data={}).status_code == 200

    # DELETE via UI
    assert client.post(f"/ui/usuarios/{alvo_id}/excluir").status_code == 200

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
