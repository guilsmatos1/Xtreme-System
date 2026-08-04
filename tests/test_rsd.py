"""Integração RSD: client HTTP (MockTransport) e rotas UI."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import Auditoria
from xtreme_system.perfil import core as perfil
from xtreme_system.rsd import core as rsd
from xtreme_system.usuario import core as usuario


def _login_html(csrf: str = "csrf-test-token") -> str:
    return (
        '<form method="post" action="/accounts/login/">'
        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">'
        '<input type="password" name="password" id="id_password">'
        "</form>"
    )


def _unitaria_html(csrf: str = "csrf-unitaria") -> str:
    return (
        '<form method="post" class="dossie-form">'
        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">'
        '<input type="radio" name="fonte" value="be" checked>'
        '<input name="placa" id="id_placa">'
        "</form>"
    )


_ROUTES: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]] = {}


def _route(
    method: str, path: str
) -> Callable[
    [Callable[[httpx.Request], httpx.Response]],
    Callable[[httpx.Request], httpx.Response],
]:
    def decorator(
        fn: Callable[[httpx.Request], httpx.Response],
    ) -> Callable[[httpx.Request], httpx.Response]:
        _ROUTES[(method, path)] = fn
        return fn

    return decorator


@_route("GET", "/accounts/login/")
def _login_get(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        text=_login_html(),
        headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
    )


@_route("POST", "/accounts/login/")
def _login_post(request: httpx.Request) -> httpx.Response:
    body = request.content.decode()
    if "password=errada" in body or "login=bad%40x.com" in body:
        return httpx.Response(200, text=_login_html())
    return httpx.Response(
        302,
        headers={
            "Location": "/dossie/unitaria/",
            "Set-Cookie": "sessionid=sess-test; Path=/",
        },
    )


@_route("POST", "/atpv/puxar-dados/")
def _puxar_dados(request: httpx.Request) -> httpx.Response:
    if "placa=FAIL1" in request.content.decode():
        return httpx.Response(422, json={"erro": "placa inválida"})
    return httpx.Response(
        200,
        json={
            "placa": "TCM9G85",
            "renavam": "01412830033",
            "chassi": "9BGEB48A0SG190437",
            "marca_modelo": "CHEV/ONIX 10MT LT2",
            "ano": 2025,
            "cor": "CINZA",
            "nome_proprietario": "XTREME MOTORS LTDA",
            "cpf_cnpj": "44237309000175",
            "tipo_documento": "CNPJ",
            "outro_estado": False,
            "origem": "novo",
        },
    )


@_route("GET", "/dossie/unitaria/")
def _unitaria_get(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=_unitaria_html())


@_route("POST", "/dossie/unitaria/")
def _unitaria_post(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(302, headers={"Location": "/dossie/351/"})


@_route("GET", "/dossie/351/status/")
def _status(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "status": "done",
            "status_display": "Concluída",
            "is_terminal": True,
            "has_consolidado": True,
            "error": None,
            "portais": [
                {"portal": "ecrv", "status": "ok", "duracao_ms": 100, "msg": ""}
            ],
        },
    )


@_route("GET", "/dossie/351/pdf/")
def _pdf(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        content=b"%PDF-1.4 mock",
        headers={"Content-Type": "application/pdf"},
    )


def _handler(request: httpx.Request) -> httpx.Response:
    fn = _ROUTES.get((request.method, request.url.path))
    if fn is None:
        return httpx.Response(404, text="not found")
    return fn(request)


def _fake_client_cls(transport: httpx.MockTransport) -> type[rsd.RsdClient]:
    class _FakeClient(rsd.RsdClient):
        def open(self) -> None:
            self._client = httpx.Client(
                base_url=self.base_url,
                transport=transport,
                timeout=5.0,
                follow_redirects=False,
            )

    return _FakeClient


@pytest.fixture
def rsd_client() -> rsd.RsdClient:
    transport = httpx.MockTransport(_handler)
    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=transport,
        timeout=5.0,
        follow_redirects=False,
    )
    return client


def test_login_e_puxar_dados(rsd_client: rsd.RsdClient) -> None:
    with rsd_client:
        rsd_client.login()
        dados = rsd_client.puxar_dados("TCM9G85")
    assert dados.marca_modelo == "CHEV/ONIX 10MT LT2"
    assert dados.ano == 2025
    mapped = rsd.mapear_para_veiculo(dados)
    assert mapped["modelo"] == "CHEV/ONIX 10MT LT2"
    assert mapped["marca"] == "CHEV"
    assert mapped["cor"] == "CINZA"
    assert mapped["chassi"] == "9BGEB48A0SG190437"


def test_login_credenciais_invalidas(rsd_client: rsd.RsdClient) -> None:
    rsd_client.senha = "errada"
    with rsd_client, pytest.raises(rsd.RsdAuthError, match="inválidos"):
        rsd_client.login()


def test_consulta_unitaria_be_e_pdf(rsd_client: rsd.RsdClient) -> None:
    with rsd_client:
        rsd_client.login()
        resultado = rsd_client.consultar_unitaria_be("TCM9G85", poll_timeout_s=5)
        assert resultado.dossie_id == 351
        assert resultado.status == "done"
        pdf = rsd_client.baixar_pdf(351)
    assert pdf.startswith(b"%PDF")


def test_puxar_dados_erro_do_portal(rsd_client: rsd.RsdClient) -> None:
    with rsd_client:
        rsd_client.login()
        with pytest.raises(rsd.RsdConsultaError, match="placa inválida"):
            rsd_client.puxar_dados("FAIL1")


def test_client_from_config_exige_credenciais(db_session: Session) -> None:
    config = rsd.get_config(db_session)
    with pytest.raises(rsd.RsdNotConfiguredError):
        rsd.client_from_config(config)


def test_atualizar_config_mascara_senha_na_auditoria(db_session: Session) -> None:
    seed = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    db_session.add(seed)
    db_session.flush()
    db_session.info["usuario_id"] = seed.id

    rsd.atualizar_config(
        db_session,
        rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123"),
        actor_id=seed.id,
    )
    db_session.flush()
    row = (
        db_session.query(Auditoria)
        .filter_by(tabela="rsd_config")
        .order_by(Auditoria.id.desc())
        .first()
    )
    assert row is not None
    depois = row.dados_depois or {}
    assert depois.get("senha") == "***"
    assert depois.get("email") == "a@b.com"


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(usuarios=[("admin", usuario.Papel.admin)])


def _login_ui(client: TestClient) -> None:
    resp = client.post(
        "/ui/login",
        data={"username": "admin", "password": "senha"},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)


def _salvar_config_rsd(client: TestClient) -> None:
    resp = client.post(
        "/ui/configuracoes/rsd",
        data={
            "email": "loja@test.com",
            "senha": "segredo",
            "base_url": "https://rsd.test",
        },
    )
    assert resp.status_code == 200


def _patch_client_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cls = _fake_client_cls(httpx.MockTransport(_handler))
    monkeypatch.setattr(
        rsd,
        "client_from_config",
        lambda config: fake_cls(
            base_url=config.base_url, email=config.email, senha=config.senha
        ),
    )


def test_ui_puxar_dados_sem_config(client: TestClient) -> None:
    _login_ui(client)
    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "ABC1D23"})
    assert resp.status_code == 400
    assert "Configure" in resp.text or "configur" in resp.text.lower()


def test_ui_puxar_dados_com_mock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "TCM9G85"})
    assert resp.status_code == 200
    assert "Dados carregados" in resp.text
    assert "CHEV/ONIX" in resp.text


def test_ui_consulta_unitaria_com_mock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post("/ui/rsd/consulta-unitaria", data={"placa": "TCM9G85"})
    assert resp.status_code == 200
    assert "351" in resp.text
    assert "/ui/rsd/dossie/351/pdf" in resp.text


def test_ui_pdf_com_mock(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.get("/ui/rsd/dossie/351/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


def test_pagina_da_rota_rsd_mapeia_para_veiculos() -> None:
    assert perfil.pagina_da_rota("/ui/rsd/puxar-dados") == "veiculos"
    assert perfil.pagina_da_rota("/ui/rsd/dossie/1/pdf") == "veiculos"
