"""Integração RSD: client HTTP (MockTransport) e rotas UI."""

from __future__ import annotations

import html.parser
import json
import re
import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xtreme_system.api.routes.ui_routes import rsd as rsd_routes
from xtreme_system.auditoria.core import Auditoria
from xtreme_system.database.core import SessionLocal
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.rsd import core as rsd
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


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
    if "placa=FAI1L23" in request.content.decode():
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
            "uf": "SP",
            "outro_estado": False,
            "origem": "novo",
        },
    )


@_route("GET", "/atpv/nova/")
def _atpv_nova(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        text=(
            '<form action="/atpv/puxar-dados/" name="puxar"><input name="placa"></form>'
        ),
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


@pytest.fixture(autouse=True)
def _reset_rsd_client_cache() -> Iterator[None]:
    """Evita client HTTP em cache vazar entre testes (ver client_from_config)."""
    yield
    rsd.invalidar_client_cache()


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
    assert mapped["modelo"] == "ONIX 10MT LT2"
    assert mapped["marca"] == "CHEV"
    assert mapped["cor"] == "CINZA"
    assert mapped["chassi"] == "9BGEB48A0SG190437"
    assert mapped["proprietario_documento"] == "44237309000175"
    assert "proprietario_uf" not in mapped


def test_mapear_para_veiculo_preserva_modelo_sem_separador() -> None:
    mapped = rsd.mapear_para_veiculo(
        rsd.PuxarDadosResult(marca_modelo="MODELO SEM MARCA")
    )
    assert mapped == {"modelo": "MODELO SEM MARCA"}


def test_puxar_dados_reloga_apos_redirect_de_sessao() -> None:
    puxar_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal puxar_calls
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            puxar_calls += 1
            if puxar_calls == 1:
                return httpx.Response(302, headers={"Location": "/accounts/login/"})
            return httpx.Response(200, json={"marca_modelo": "CHEV/ONIX"})
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client:
        client.login()
        dados = client.puxar_dados("TCM9G85")

    assert puxar_calls == 2
    assert dados.marca_modelo == "CHEV/ONIX"


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
            rsd_client.puxar_dados("FAI1L23")


def test_puxar_dados_timeout_vira_erro_da_integracao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            raise httpx.ReadTimeout("portal sem resposta", request=request)
        return _handler(request)

    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client:
        client.login()
        with pytest.raises(rsd.RsdTimeoutError, match="não respondeu a tempo"):
            client.puxar_dados("TCM9G85")


def test_puxar_dados_payload_invalido_vira_erro_da_integracao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            return httpx.Response(200, json={"ano": {"nao": "é ano"}})
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client, pytest.raises(rsd.RsdConsultaError, match="Resposta inválida"):
        client.puxar_dados("TCM9G85")


def test_puxar_dados_falha_de_conexao_vira_erro_da_integracao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            raise httpx.ConnectError("portal indisponível", request=request)
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client, pytest.raises(rsd.RsdConsultaError, match="Falha ao comunicar"):
        client.puxar_dados("TCM9G85")


def test_iniciar_unitaria_falha_de_conexao_vira_erro_da_integracao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.method == "GET" and request.url.path == "/dossie/unitaria/":
            raise httpx.ConnectError("portal indisponível", request=request)
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test", email="loja@test.com", senha="segredo"
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client, pytest.raises(rsd.RsdConsultaError, match="Falha ao comunicar"):
        client.iniciar_unitaria("TCM9G85")


def test_iniciar_unitaria_reloga_apos_sessao_expirada() -> None:
    unitaria_gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal unitaria_gets
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.method == "GET" and request.url.path == "/dossie/unitaria/":
            unitaria_gets += 1
            # Sessão expirada na 1a tentativa: portal devolve a própria
            # página de login (200) em vez do formulário da unitária.
            if unitaria_gets == 1:
                return httpx.Response(200, text=_login_html())
            return httpx.Response(200, text=_unitaria_html())
        if request.method == "POST" and request.url.path == "/dossie/unitaria/":
            return httpx.Response(302, headers={"Location": "/dossie/351/"})
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test", email="loja@test.com", senha="segredo"
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client:
        dossie_id = client.iniciar_unitaria("TCM9G85")

    assert dossie_id == 351
    assert unitaria_gets == 2


def test_iniciar_unitaria_reconstroi_csrf_do_formulario_apos_relogin() -> None:
    login_gets = 0
    login_posts = 0
    unitarias = 0
    posts: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_gets, login_posts, unitarias
        if request.method == "GET" and request.url.path == "/accounts/login/":
            login_gets += 1
            return httpx.Response(
                200,
                text=_login_html(f"login-csrf-{login_gets}"),
                headers={"Set-Cookie": f"csrftoken=login-cookie-{login_gets}; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            login_posts += 1
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": f"sessionid=session-{login_posts}; Path=/",
                },
            )
        if request.method == "GET" and request.url.path == "/dossie/unitaria/":
            unitarias += 1
            return httpx.Response(
                200, text=_unitaria_html(f"unitaria-csrf-{unitarias}")
            )
        if request.method == "POST" and request.url.path == "/dossie/unitaria/":
            body = request.content.decode()
            posts.append((request.headers.get("X-CSRFToken", ""), body))
            if len(posts) == 1:
                return httpx.Response(403)
            assert posts[-1][0] == "unitaria-csrf-2"
            assert "csrfmiddlewaretoken=unitaria-csrf-2" in posts[-1][1]
            return httpx.Response(302, headers={"Location": "/dossie/351/"})
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test", email="loja@test.com", senha="segredo"
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client:
        assert client.iniciar_unitaria("TCM9G85") == 351

    assert login_posts == 2
    assert unitarias == 2
    assert len(posts) == 2


def test_testar_conexao_rejeita_capacidade_rsd_bloqueada() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(200, text=_login_html())
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.method == "GET" and request.url.path == "/dossie/unitaria/":
            return httpx.Response(200, text=_unitaria_html())
        if request.method == "GET" and request.url.path == "/atpv/nova/":
            return httpx.Response(403, text="sem assinatura")
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test", email="loja@test.com", senha="segredo"
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client, pytest.raises(rsd.RsdCapabilityError, match="puxar dados"):
        client.testar_conexao()


def test_testar_conexao_valida_as_duas_capacidades_sem_criar_dossie(
    rsd_client: rsd.RsdClient,
) -> None:
    with rsd_client:
        rsd_client.testar_conexao()


def test_status_unitaria_falha_de_conexao_vira_erro_da_integracao(
    rsd_client: rsd.RsdClient,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dossie/999/status/":
            raise httpx.ConnectError("portal indisponível", request=request)
        return _handler(request)

    rsd_client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )
    with rsd_client:
        rsd_client.login()
        with pytest.raises(rsd.RsdConsultaError, match="Falha ao comunicar"):
            rsd_client.status_unitaria(999)


def test_status_unitaria_reloga_apos_redirect_de_sessao() -> None:
    status_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal status_calls
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.url.path == "/dossie/351/status/":
            status_calls += 1
            if status_calls == 1:
                return httpx.Response(302, headers={"Location": "/accounts/login/"})
            return httpx.Response(
                200,
                json={"status": "done", "is_terminal": True, "has_consolidado": True},
            )
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test", email="loja@test.com", senha="segredo"
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client:
        client.login()
        resultado = client.status_unitaria(351)

    assert status_calls == 2
    assert resultado.status == "done"
    assert resultado.is_terminal


def test_baixar_pdf_falha_de_conexao_vira_erro_da_integracao(
    rsd_client: rsd.RsdClient,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dossie/351/pdf/":
            raise httpx.ConnectError("portal indisponível", request=request)
        return _handler(request)

    rsd_client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )
    with rsd_client:
        rsd_client.login()
        with pytest.raises(rsd.RsdConsultaError, match="Falha ao comunicar"):
            rsd_client.baixar_pdf(351)


def test_baixar_pdf_reloga_ao_encontrar_pagina_de_login() -> None:
    pdf_gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal pdf_gets
        if request.method == "GET" and request.url.path == "/accounts/login/":
            return httpx.Response(
                200,
                text=_login_html(),
                headers={"Set-Cookie": "csrftoken=cookie-csrf; Path=/"},
            )
        if request.method == "POST" and request.url.path == "/accounts/login/":
            return httpx.Response(
                302,
                headers={
                    "Location": "/dossie/unitaria/",
                    "Set-Cookie": "sessionid=sess-test; Path=/",
                },
            )
        if request.url.path == "/dossie/351/pdf/":
            pdf_gets += 1
            if pdf_gets == 1:
                # follow_redirects=True: portal expira sessão e devolve o
                # HTML de login com 200 em vez do PDF.
                return httpx.Response(200, text=_login_html())
            return httpx.Response(
                200,
                content=b"%PDF-1.4 mock",
                headers={"Content-Type": "application/pdf"},
            )
        return httpx.Response(404)

    client = rsd.RsdClient(
        base_url="https://rsd.test", email="loja@test.com", senha="segredo"
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )

    with client:
        client.login()
        pdf = client.baixar_pdf(351)

    assert pdf_gets == 2
    assert pdf.startswith(b"%PDF")


def test_poll_status_tolera_falhas_transitorias_e_depois_recupera(
    rsd_client: rsd.RsdClient,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path == "/dossie/351/status/":
            calls += 1
            if calls <= 2:
                raise httpx.ConnectError("portal indisponível", request=request)
            return httpx.Response(
                200,
                json={"status": "done", "is_terminal": True, "has_consolidado": True},
            )
        return _handler(request)

    rsd_client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )
    with rsd_client:
        rsd_client.login()
        payload = rsd_client._poll_status(351, timeout_s=30)  # noqa: SLF001

    assert calls == 3
    assert payload["status"] == "done"


def test_poll_status_desiste_apos_falhas_consecutivas_persistentes(
    rsd_client: rsd.RsdClient,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dossie/351/status/":
            raise httpx.ConnectError("portal indisponível", request=request)
        return _handler(request)

    rsd_client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )
    with rsd_client:
        rsd_client.login()
        with pytest.raises(rsd.RsdConsultaError, match="Falha ao comunicar"):
            rsd_client._poll_status(351, timeout_s=30)  # noqa: SLF001


def test_decriptar_senha_avisa_quando_ciphertext_nao_decripta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    avisos: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rsd.logger, "warning", lambda event, **kw: avisos.append({"event": event, **kw})
    )
    # Tem cara de token Fernet (prefixo gAAAAA) mas não decripta com a
    # chave atual — deve ser tratado como chave rotacionada, não senha
    # legada em texto plano.
    valor = "gAAAAA-token-invalido-para-a-chave-atual"

    with pytest.raises(rsd.RsdEncryptionError):
        rsd._decriptar_senha(valor)  # noqa: SLF001
    assert any(
        a["event"] == "rsd_decriptar_senha_falhou_chave_invalida" for a in avisos
    )
    assert valor not in repr(avisos)


def test_decriptar_senha_legado_texto_plano_nao_avisa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    avisos: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rsd.logger, "warning", lambda event, **kw: avisos.append({"event": event, **kw})
    )

    with pytest.raises(rsd.RsdEncryptionError):
        rsd._decriptar_senha("senha-legada-texto-plano")  # noqa: SLF001

    assert avisos


def test_client_from_config_exige_credenciais(db_session: Session) -> None:
    config = rsd.get_config(db_session)
    with pytest.raises(rsd.RsdNotConfiguredError):
        rsd.client_from_config(config)


@pytest.mark.parametrize(
    "target_url",
    [
        "http://lojas.rsdsistema.com.br",
        "https://localhost",
        "https://127.0.0.1",
        "https://usuario:senha@lojas.rsdsistema.com.br",
        "https://atacante.example",
        "https://lojas.rsdsistema.com.br:8443",
    ],
)
def test_client_from_values_rejeita_destinos_de_url_inseguros(
    target_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = rsd.RsdConfig(email="loja@test.com", senha="not-used")
    monkeypatch.setattr(
        rsd,
        "RsdClient",
        lambda **_kwargs: pytest.fail("cliente não deve ser construído"),
    )

    with pytest.raises(rsd.RsdConfigError):
        rsd.client_from_values(
            email="loja@test.com",
            senha="segredo",
            base_url=target_url,
            config=config,
        )


def test_client_from_values_rejeita_dns_privado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RSD_ALLOWED_HOSTS", "portal.interno.example")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("10.0.0.8", 443)),
        ],
    )
    config = rsd.RsdConfig(email="loja@test.com", senha="not-used")

    with pytest.raises(rsd.RsdConfigError, match="destino"):
        rsd.client_from_values(
            email="loja@test.com",
            senha="segredo",
            base_url="https://portal.interno.example",
            config=config,
        )


def test_redirect_externo_e_bloqueado_antes_de_nova_requisicao() -> None:
    chamadas = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(
            302, headers={"Location": "https://atacante.example/roubar"}
        )

    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )

    with client, pytest.raises(rsd.RsdConfigError):
        client._request("GET", "/dossie/351/pdf/", follow_redirects=True)  # noqa: SLF001

    assert chamadas == 1


def test_ciphertext_invalido_nao_constroi_cliente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = rsd.RsdConfig(email="loja@test.com", senha="gAAAAA-token-de-outra-chave")
    monkeypatch.setattr(
        rsd,
        "RsdClient",
        lambda **_kwargs: pytest.fail("cliente não deve ser construído"),
    )
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **_kwargs: pytest.fail("transporte HTTP não deve ser criado"),
    )

    with pytest.raises(rsd.RsdEncryptionError):
        rsd.client_from_config(config)


def test_revogar_config_apaga_banco_cache_e_audita(db_session: Session) -> None:
    admin = usuario.Usuario(
        username="revoker", senha_hash="x", papel=usuario.Papel.admin
    )
    db_session.add(admin)
    db_session.flush()
    config = rsd.atualizar_config(
        db_session,
        rsd.RsdConfigUpdate(email="loja@test.com", senha="segredo"),
        actor_id=admin.id,
    )
    client = rsd.client_from_config(config)

    revogada = rsd.revogar_config(db_session, admin.id)

    assert revogada.email == ""
    assert revogada.senha == ""
    assert revogada.revogada
    assert client._client is None  # noqa: SLF001
    with pytest.raises(rsd.RsdNotConfiguredError):
        rsd.client_from_config(revogada)
    audit = (
        db_session.query(Auditoria)
        .filter_by(tabela="rsd_config", tipo_acao="REVOKE")
        .order_by(Auditoria.id.desc())
        .first()
    )
    assert audit is not None


def test_csrf_invalido_bloqueia_salvar_rsd_antes_da_integracao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(client)
    monkeypatch.setattr(
        rsd,
        "RsdClient",
        lambda **_kwargs: pytest.fail("RSD não deve ser chamado"),
    )

    response = client.post(
        "/ui/configuracoes/rsd",
        data={
            "email": "loja@test.com",
            "senha": "segredo",
            "base_url": "https://rsd.test",
        },
    )

    assert response.status_code == 403


def test_csrf_valido_e_origem_invalida_e_rejeitada(client: TestClient) -> None:
    _login_ui(client)
    token = str(client.cookies.get("csrf_token"))
    response = client.post(
        "/ui/configuracoes/rsd/teste",
        data={
            "email": "loja@test.com",
            "senha": "segredo",
            "base_url": "https://rsd.test",
            "csrf_token": token,
        },
        headers={"Origin": "https://atacante.example"},
    )

    assert response.status_code == 403


def test_settings_rejeita_chave_rsd_fraca_ou_igual_a_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = "a1b2c3d4" * 8
    monkeypatch.setenv("AUTH_SECRET_KEY", shared)
    with pytest.raises(ValueError, match="diferente"):
        rsd.Settings(rsd_encryption_key=shared)
    with pytest.raises(ValueError, match="entropia"):
        rsd.Settings(rsd_encryption_key="x" * 32)


def test_cache_expira_cliente_ocioso(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo")
    )
    agora = 10_000.0
    monkeypatch.setattr(time, "monotonic", lambda: agora)
    primeiro = rsd.client_from_config(config)
    agora += rsd._CLIENT_CACHE_TTL_S + 1  # noqa: SLF001
    segundo = rsd.client_from_config(config)

    assert segundo is not primeiro
    assert primeiro._client is None  # noqa: SLF001


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


def test_client_from_config_reaproveita_client_entre_chamadas(
    db_session: Session,
) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )

    primeiro = rsd.client_from_config(config)
    segundo = rsd.client_from_config(config)

    assert primeiro is segundo


def test_invalidar_client_cache_fecha_clients_em_cache(db_session: Session) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )
    client = rsd.client_from_config(config)
    assert getattr(client, "_client", None) is not None

    rsd.invalidar_client_cache()

    assert client._client is None  # noqa: SLF001
    novo_client = rsd.client_from_config(config)
    assert novo_client is not client


def test_client_cacheado_invalidado_nao_reabre_sessao_antiga(
    db_session: Session,
) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )
    antigo = rsd.client_from_config(config)

    rsd.invalidar_client_cache()

    with pytest.raises(rsd.RsdClientRetiredError):
        antigo._http()  # noqa: SLF001


def test_invalidacao_aguarda_consulta_em_voo_antes_de_fechar_cliente(
    db_session: Session,
) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )
    client = rsd.client_from_config(config)
    entrou_no_portal = threading.Event()
    liberar_portal = threading.Event()

    def handler(_request: httpx.Request) -> httpx.Response:
        entrou_no_portal.set()
        assert liberar_portal.wait(timeout=2)
        return httpx.Response(
            200,
            json={"placa": "TCM9G85", "marca_modelo": "CHEV/ONIX"},
        )

    assert client._client is not None  # noqa: SLF001
    client._client.close()  # noqa: SLF001
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )
    client._client.cookies.set("sessionid", "sess-test")  # noqa: SLF001
    client._csrf = "csrf-test"  # noqa: SLF001
    resultado: list[rsd.PuxarDadosResult] = []

    worker = threading.Thread(
        target=lambda: resultado.append(client.puxar_dados("TCM9G85"))
    )
    worker.start()
    assert entrou_no_portal.wait(timeout=2)

    invalidador = threading.Thread(target=rsd.invalidar_client_cache)
    invalidador.start()
    time.sleep(0.02)
    assert invalidador.is_alive()

    liberar_portal.set()
    worker.join(timeout=2)
    invalidador.join(timeout=2)

    assert not worker.is_alive()
    assert not invalidador.is_alive()
    assert resultado[0].marca_modelo == "CHEV/ONIX"
    assert client._client is None  # noqa: SLF001


def test_atualizar_config_criptografa_senha_em_repouso(db_session: Session) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )
    assert config.senha != "segredo123"

    client = rsd.client_from_config(config)
    assert client.senha == ""


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
    csrf_token = client.cookies.get("csrf_token")
    assert csrf_token
    resp = client.post(
        "/ui/configuracoes/rsd",
        data={
            "email": "loja@test.com",
            "senha": "segredo",
            "base_url": "https://rsd.test",
            "csrf_token": csrf_token,
        },
    )
    assert resp.status_code == 200


def test_salvar_config_rsd_duas_vezes_sem_reenviar_senha_nao_reencripta(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-salvar só o e-mail (senha em branco = 'manter atual') não pode
    repassar o ciphertext já salvo pra `atualizar_config` como se fosse a
    senha em texto puro — isso reencriptaria o ciphertext e corromperia a
    senha a cada re-save (ver docs/analise-erros-rsd.md)."""
    chamadas: list[rsd.RsdConfigUpdate] = []
    original = rsd.atualizar_config

    def _fake_atualizar_config(
        session: Session, data: rsd.RsdConfigUpdate, actor_id: int | None = None
    ) -> rsd.RsdConfig:
        chamadas.append(data)
        return original(session, data, actor_id)

    monkeypatch.setattr(rsd, "atualizar_config", _fake_atualizar_config)

    _login_ui(client)
    _salvar_config_rsd(client)  # 1a vez: email + senha

    resp = client.post(
        "/ui/configuracoes/rsd",
        data={"email": "novo@test.com", "senha": "", "base_url": "https://rsd.test"},
        headers={"X-CSRFToken": str(client.cookies.get("csrf_token"))},
    )
    assert resp.status_code == 200

    assert len(chamadas) == 2
    # Senha em branco no formulário deve chegar em branco em atualizar_config
    # (que já sabe manter a atual) — não como o ciphertext salvo antes.
    assert chamadas[1].senha == ""


def test_ui_teste_conexao_usa_valores_do_formulario_nao_do_banco(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O botão 'Testar conexão' deve testar o que está no formulário, não a
    config já persistida (que pode estar vazia/desatualizada)."""
    _login_ui(client)
    # Nada foi salvo ainda — config no banco está vazia.
    recebido: dict[str, str] = {}

    class _CapturaClient:
        def __init__(self, *, base_url: str, email: str, senha: str) -> None:
            recebido["base_url"] = base_url
            recebido["email"] = email
            recebido["senha"] = senha

        def open(self) -> None:
            return None

        def close(self) -> None:
            return None

        def testar_conexao(self) -> None:
            return None

    monkeypatch.setattr(rsd, "RsdClient", _CapturaClient)

    resp = client.post(
        "/ui/configuracoes/rsd/teste",
        data={
            "email": "digitado@test.com",
            "senha": "senha-digitada",
            "base_url": "https://rsd.test",
        },
        headers={"X-CSRFToken": str(client.cookies.get("csrf_token"))},
    )

    assert resp.status_code == 200
    assert "Conexão com o portal RSD OK." in resp.text
    assert 'value="digitado@test.com"' in resp.text
    assert 'value="https://rsd.test"' in resp.text
    assert "Conexão testada, ainda não salva" in resp.text
    assert "senha-digitada" not in resp.text
    assert recebido == {
        "base_url": "https://rsd.test",
        "email": "digitado@test.com",
        "senha": "senha-digitada",
    }


@pytest.mark.parametrize(
    "erro",
    [
        rsd.RsdAuthError("E-mail ou senha inválidos no portal RSD."),
        rsd.RsdTimeoutError("O portal RSD não respondeu a tempo. Tente novamente."),
    ],
    ids=["autenticacao", "timeout"],
)
def test_ui_teste_conexao_com_erro_preserva_rascunho_sem_expor_senha(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    erro: rsd.RsdError,
) -> None:
    class _ErroClient:
        def open(self) -> None:
            return None

        def close(self) -> None:
            return None

        def testar_conexao(self) -> None:
            raise erro

    _login_ui(client)
    monkeypatch.setattr(
        rsd,
        "client_from_values",
        lambda **_kwargs: _ErroClient(),
    )

    resp = client.post(
        "/ui/configuracoes/rsd/teste",
        data={
            "email": "rascunho@test.com",
            "senha": "senha-super-secreta",
            "base_url": "https://rsd.test",
            "csrf_token": str(client.cookies.get("csrf_token")),
        },
    )

    assert resp.status_code == 400
    assert 'value="rascunho@test.com"' in resp.text
    assert 'value="https://rsd.test"' in resp.text
    assert "senha-super-secreta" not in resp.text
    assert str(erro) in resp.text


def test_ui_teste_conexao_sem_config_salva_e_sem_form_da_erro_configuracao(
    client: TestClient,
) -> None:
    _login_ui(client)
    resp = client.post(
        "/ui/configuracoes/rsd/teste",
        data={"csrf_token": str(client.cookies.get("csrf_token"))},
    )
    assert resp.status_code == 400
    assert "Configure" in resp.text or "configur" in resp.text.lower()


@pytest.mark.parametrize(
    "path",
    [
        "/ui/configuracoes/rsd",
        "/ui/configuracoes/rsd/teste",
        "/ui/configuracoes/rsd/revogar",
    ],
)
@pytest.mark.parametrize("username", [None, "func"], ids=["anonimo", "funcionario"])
def test_rotas_de_credenciais_rsd_bloqueiam_acesso_sem_admin(
    make_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    username: str | None,
) -> None:
    def _side_effect(**_kwargs: object) -> None:
        pytest.fail("rota de credencial não deve produzir side effect")

    monkeypatch.setattr(rsd, "atualizar_config", _side_effect)
    monkeypatch.setattr(rsd, "client_from_values", _side_effect)
    monkeypatch.setattr(rsd, "revogar_config", _side_effect)

    client = make_client(
        usuarios=[("func", usuario.Papel.funcionario)] if username else None
    )
    if username:
        _login_ui_as(client, username)

    response = client.post(
        path,
        data={"csrf_token": str(client.cookies.get("csrf_token"))},
        follow_redirects=False,
    )

    if username is None:
        assert response.status_code in (302, 303)
        assert "/ui/login" in response.headers.get("location", "")
    else:
        assert response.status_code == 403


def _login_ui_as(client: TestClient, username: str) -> None:
    response = client.post(
        "/ui/login",
        data={"username": username, "password": "senha"},
        follow_redirects=False,
    )
    assert response.status_code in (200, 302, 303)


def test_admin_pode_revogar_credencial_rsd_pela_rota(client: TestClient) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)

    response = client.post(
        "/ui/configuracoes/rsd/revogar",
        data={"csrf_token": str(client.cookies.get("csrf_token"))},
    )

    assert response.status_code == 200
    assert "Credencial RSD revogada e removida." in response.text
    assert "Integração não configurada" in response.text


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
    assert 'role="alert"' in resp.text
    assert 'id="rsd-status"' in resp.text


def test_ui_puxar_dados_placa_vazia(client: TestClient) -> None:
    _login_ui(client)
    resp = client.post("/ui/rsd/puxar-dados", data={"placa": ""})
    assert resp.status_code == 400
    assert "Informe a placa" in resp.text
    assert 'role="alert"' in resp.text
    assert "data-rsd-campos=" not in resp.text


def test_ui_puxar_dados_placa_invalida(client: TestClient) -> None:
    _login_ui(client)
    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "XX"})
    assert resp.status_code == 400
    assert "Placa inválida" in resp.text
    assert 'role="alert"' in resp.text
    assert "data-rsd-campos=" not in resp.text


def test_ui_puxar_dados_com_mock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    # HX-Request ativa o middleware _htmx_write_feedback; sem HX-Trigger
    # próprio ele fecharia o modal antes do JS aplicar data-rsd-campos.
    resp = client.post(
        "/ui/rsd/puxar-dados",
        data={"placa": "TCM9G85"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "Dados carregados do RSD." in resp.text
    assert "alert--success" in resp.text
    assert "ONIX 10MT LT2" in resp.text
    assert "CHEV/ONIX 10MT LT2" not in resp.text
    assert "<script>" not in resp.text

    # |tojson|e deixa aspas cruas no atributo (Markup); o browser só lê "{".
    # forceescape garante JSON parseável via getAttribute / HTML parser.
    class _CamposAttr(html.parser.HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.value: str | None = None

        def handle_starttag(
            self, _tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if self.value is not None:
                return
            found = dict(attrs).get("data-rsd-campos")
            if found is not None:
                self.value = found

    parser = _CamposAttr()
    parser.feed(resp.text)
    assert parser.value is not None
    campos = json.loads(parser.value)
    assert campos.get("modelo") == "ONIX 10MT LT2"
    assert campos.get("marca") == "CHEV"
    assert len(parser.value) > 2  # não só "{"

    trigger = json.loads(resp.headers["HX-Trigger"])
    assert "htmx:close-modal" not in trigger
    assert "htmx:toast" not in trigger


def test_ui_puxar_dados_timeout_retorna_feedback_htmx(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _TimeoutClient:
        def __enter__(self) -> _TimeoutClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def puxar_dados(self, _placa: str) -> rsd.PuxarDadosResult:
            raise rsd.RsdTimeoutError(
                "O portal RSD não respondeu a tempo ao puxar os dados. Tente novamente."
            )

    _login_ui(client)
    _salvar_config_rsd(client)
    monkeypatch.setattr(rsd, "client_from_config", lambda _config: _TimeoutClient())

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "TCM9G85"})

    assert resp.status_code == 400
    assert "não respondeu a tempo" in resp.text
    assert 'role="alert"' in resp.text
    assert 'id="rsd-status"' in resp.text


def test_ui_puxar_dados_com_prefixo_de_wizard(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post(
        "/ui/rsd/puxar-dados",
        data={
            "vei_placa": "TCM9G85",
            "rsd_prefix": "vei_",
            "rsd_status_id": "rsd-status-compra",
        },
    )
    assert resp.status_code == 200
    assert 'id="rsd-status-compra"' in resp.text
    assert "data-rsd-campos=" in resp.text
    assert "vei_modelo" in resp.text
    assert "ONIX 10MT LT2" in resp.text
    assert "alert--success" in resp.text


def _ultima_consulta(**filtros: object) -> rsd.RsdConsulta | None:
    # Sessão própria: `registrar_consulta`/`atualizar_consulta_dossie` também
    # abrem a sua (ver docstring), pois a sessão do request já foi encerrada
    # por `detach_request_session` quando o resultado do portal chega.
    session = SessionLocal()
    try:
        return (
            session.query(rsd.RsdConsulta)
            .filter_by(**filtros)
            .order_by(rsd.RsdConsulta.id.desc())
            .first()
        )
    finally:
        session.close()


def test_registrar_consulta_grava_sucesso(db_session: Session) -> None:
    seed = usuario.Usuario(username="rsd-op", senha_hash="x", papel=usuario.Papel.admin)
    db_session.add(seed)
    # registrar_consulta abre sessão própria, então precisa estar commitado
    db_session.commit()

    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.puxar_dados,
        placa="TCM9G85",
        usuario_id=seed.id,
        payload={"marca_modelo": "CHEV/ONIX", "senha": "nao-deve-aparecer"},
        campos_aplicados={"modelo": "ONIX"},
        sucesso=True,
    )

    registro = _ultima_consulta(tipo=rsd.TipoConsultaRsd.puxar_dados, placa="TCM9G85")
    assert registro is not None
    assert registro.sucesso is True
    assert registro.usuario_id == seed.id
    assert registro.payload == {"marca_modelo": "CHEV/ONIX"}
    assert registro.campos_aplicados == {"modelo": "ONIX"}


def test_registrar_consulta_grava_erro(db_session: Session) -> None:  # noqa: ARG001
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.unitaria,
        placa="FAIL1",
        sucesso=False,
        erro="placa inválida",
    )

    registro = _ultima_consulta(tipo=rsd.TipoConsultaRsd.unitaria, placa="FAIL1")
    assert registro is not None
    assert registro.sucesso is False
    assert registro.erro == "placa inválida"
    assert registro.payload is None


def test_atualizar_consulta_dossie_marca_terminal(db_session: Session) -> None:  # noqa: ARG001
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.unitaria,
        placa="TCM9G85",
        sucesso=True,
        dossie_id=987,
        status_dossie="processing",
    )
    rsd.atualizar_consulta_dossie(
        dossie_id=987,
        payload={"status": "done", "has_consolidado": True},
        status_dossie="done",
        sucesso=True,
    )

    registro = _ultima_consulta(dossie_id=987)
    assert registro is not None
    assert registro.status_dossie == "done"
    assert registro.payload == {"status": "done", "has_consolidado": True}


def test_ui_puxar_dados_registra_consulta_sucesso(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rsd, "registrar_consulta", lambda **kwargs: chamadas.append(kwargs)
    )
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "TCM9G85"})
    assert resp.status_code == 200

    assert len(chamadas) == 1
    chamada = chamadas[0]
    assert chamada["tipo"] == rsd.TipoConsultaRsd.puxar_dados
    assert chamada["sucesso"] is True
    assert chamada["payload"]["marca_modelo"] == "CHEV/ONIX 10MT LT2"
    assert chamada["campos_aplicados"]["modelo"] == "ONIX 10MT LT2"


def test_ui_puxar_dados_registra_consulta_erro(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rsd, "registrar_consulta", lambda **kwargs: chamadas.append(kwargs)
    )
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "FAI1L23"})
    assert resp.status_code == 400

    assert len(chamadas) == 1
    assert chamadas[0]["sucesso"] is False
    assert "placa inválida" in chamadas[0]["erro"]


def test_ui_consulta_unitaria_registra_consulta(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    inicios: list[dict[str, object]] = []
    atualizacoes: list[dict[str, object]] = []
    monkeypatch.setattr(
        rsd, "registrar_consulta", lambda **kwargs: inicios.append(kwargs)
    )
    monkeypatch.setattr(
        rsd, "atualizar_consulta_dossie", lambda **kwargs: atualizacoes.append(kwargs)
    )
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post("/ui/rsd/consulta-unitaria", data={"placa": "TCM9G85"})
    assert resp.status_code == 200
    assert len(inicios) == 1
    assert inicios[0]["dossie_id"] == 351
    assert inicios[0]["status_dossie"] == "processing"
    assert not atualizacoes

    resp = client.get("/ui/rsd/dossie/351/status")
    assert resp.status_code == 200
    assert len(atualizacoes) == 1
    assert atualizacoes[0]["dossie_id"] == 351
    assert atualizacoes[0]["status_dossie"] == "done"
    assert atualizacoes[0]["sucesso"] is True


def test_ui_dossie_status_erro_transitorio_nao_zera_estado_e_continua_poll(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um blip de rede no poll não deve sobrescrever o dossiê nem parar o
    polling do lado do cliente (achados #3 e #7 da análise)."""
    rsd_routes._poll_falhas.clear()  # noqa: SLF001

    atualizacoes: list[dict[str, object]] = []
    monkeypatch.setattr(
        rsd, "atualizar_consulta_dossie", lambda **kwargs: atualizacoes.append(kwargs)
    )

    class _FlakyClient:
        def __enter__(self) -> _FlakyClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def status_unitaria(self, _dossie_id: int) -> rsd.UnitariaResult:
            raise rsd.RsdConsultaError("Falha ao comunicar com o portal RSD.")

    _login_ui(client)
    _salvar_config_rsd(client)
    monkeypatch.setattr(rsd, "client_from_config", lambda _config: _FlakyClient())

    resp = client.get("/ui/rsd/dossie/351/status")

    assert resp.status_code == 200
    assert "hx-trigger" in resp.text
    assert not atualizacoes

    rsd_routes._poll_falhas.clear()  # noqa: SLF001


def test_ui_dossie_status_desiste_apos_falhas_persistentes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rsd_routes._poll_falhas.clear()  # noqa: SLF001

    atualizacoes: list[dict[str, object]] = []
    monkeypatch.setattr(
        rsd, "atualizar_consulta_dossie", lambda **kwargs: atualizacoes.append(kwargs)
    )

    class _AlwaysFailsClient:
        def __enter__(self) -> _AlwaysFailsClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def status_unitaria(self, _dossie_id: int) -> rsd.UnitariaResult:
            raise rsd.RsdConsultaError("Falha ao comunicar com o portal RSD.")

    _login_ui(client)
    _salvar_config_rsd(client)
    monkeypatch.setattr(rsd, "client_from_config", lambda _config: _AlwaysFailsClient())

    for _ in range(rsd_routes._POLL_TRANSIENT_MAX - 1):  # noqa: SLF001
        resp = client.get("/ui/rsd/dossie/351/status")
        assert resp.status_code == 200

    resp_final = client.get("/ui/rsd/dossie/351/status")
    assert resp_final.status_code == 400
    assert len(atualizacoes) == 1
    assert atualizacoes[0]["sucesso"] is False

    rsd_routes._poll_falhas.clear()  # noqa: SLF001


def test_ui_consulta_unitaria_com_mock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.post("/ui/rsd/consulta-unitaria", data={"placa": "TCM9G85"})
    assert resp.status_code == 200
    assert "351" in resp.text
    assert "hx-trigger" in resp.text
    assert "/ui/rsd/dossie/351/pdf" not in resp.text

    resp = client.get("/ui/rsd/dossie/351/status")
    assert resp.status_code == 200
    assert "/ui/rsd/dossie/351/pdf" in resp.text
    assert "hx-trigger" not in resp.text


def test_ui_pdf_com_mock(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _login_ui(client)
    _salvar_config_rsd(client)
    _patch_client_from_config(monkeypatch)

    resp = client.get("/ui/rsd/dossie/351/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


# ---- Atualizar veículo pelo RSD (página de detalhes) ----


def _seed_veiculo(session: Session) -> None:
    """Cria investidor + veículo e commita.

    O commit é obrigatório: a rota grava o veículo por `SessionLocal()` (a
    sessão do request já foi encerrada por `detach_request_session`), então o
    registro precisa estar visível fora da sessão do `TestClient`.
    """
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Investidor RSD"))
    veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Modelo Antigo",
            marca="MARCA ANTIGA",
            cor="PRETO",
            ano=2010,
            placa="TCM9G85",
            investidor_id=inv.id,
        ),
    )
    session.commit()


@pytest.fixture
def veiculo_client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(usuarios=[("admin", usuario.Papel.admin)], seed=_seed_veiculo)


def _veiculo_por_placa(placa: str) -> veiculo.Veiculo | None:
    session = SessionLocal()
    try:
        return veiculo.get_by_placa(session, placa)
    finally:
        session.close()


def test_ui_rsd_atualizar_veiculo_grava_campos(
    veiculo_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(veiculo_client)
    _salvar_config_rsd(veiculo_client)
    _patch_client_from_config(monkeypatch)
    item = _veiculo_por_placa("TCM9G85")
    assert item is not None

    resp = veiculo_client.post(
        f"/ui/rsd/veiculos/{item.id}/atualizar",
        headers={"HX-Request": "true"},
    )

    assert resp.status_code == 204
    assert resp.headers["HX-Refresh"] == "true"
    # Sem HX-Trigger próprio o middleware _htmx_write_feedback injetaria
    # toast + close-modal neste POST /ui/.
    trigger = json.loads(resp.headers["HX-Trigger"])
    assert "htmx:close-modal" not in trigger
    assert "htmx:toast" not in trigger

    atualizado = _veiculo_por_placa("TCM9G85")
    assert atualizado is not None
    assert atualizado.modelo == "ONIX 10MT LT2"
    assert atualizado.marca == "CHEV"
    assert atualizado.ano == 2025
    assert atualizado.cor == "CINZA"
    assert atualizado.chassi == "9BGEB48A0SG190437"
    assert atualizado.renavam == "01412830033"
    assert atualizado.proprietario_atual == "XTREME MOTORS LTDA"
    assert atualizado.proprietario_documento == "44237309000175"

    registro = _ultima_consulta(placa="TCM9G85")
    assert registro is not None
    assert registro.sucesso is True
    assert registro.veiculo_id == item.id


def test_ui_rsd_atualizar_veiculo_preserva_campos_fora_do_retorno(
    veiculo_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Campos ausentes no retorno do portal não podem virar NULL.

    Garante o `exclude_unset=True` de `crud.update`: o RSD não devolve `km`
    nem `preco`, e o veículo não pode perder o que já tinha.
    """
    _login_ui(veiculo_client)
    _salvar_config_rsd(veiculo_client)
    _patch_client_from_config(monkeypatch)
    item = _veiculo_por_placa("TCM9G85")
    assert item is not None
    antes_status = item.status
    antes_investidor = item.investidor_id

    resp = veiculo_client.post(f"/ui/rsd/veiculos/{item.id}/atualizar")

    assert resp.status_code == 204
    atualizado = _veiculo_por_placa("TCM9G85")
    assert atualizado is not None
    assert atualizado.status == antes_status
    assert atualizado.investidor_id == antes_investidor


def test_ui_rsd_atualizar_veiculo_sem_config(veiculo_client: TestClient) -> None:
    _login_ui(veiculo_client)
    item = _veiculo_por_placa("TCM9G85")
    assert item is not None

    resp = veiculo_client.post(f"/ui/rsd/veiculos/{item.id}/atualizar")

    assert resp.status_code == 400
    assert 'role="alert"' in resp.text
    assert 'id="rsd-status-veiculo"' in resp.text
    inalterado = _veiculo_por_placa("TCM9G85")
    assert inalterado is not None
    assert inalterado.modelo == "Modelo Antigo"


def test_ui_rsd_atualizar_veiculo_erro_do_portal_nao_altera(
    veiculo_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _TimeoutClient:
        def puxar_dados(self, _placa: str) -> rsd.PuxarDadosResult:
            raise rsd.RsdTimeoutError(
                "O portal RSD não respondeu a tempo ao puxar os dados. Tente novamente."
            )

    _login_ui(veiculo_client)
    _salvar_config_rsd(veiculo_client)
    monkeypatch.setattr(rsd, "client_from_config", lambda _config: _TimeoutClient())
    item = _veiculo_por_placa("TCM9G85")
    assert item is not None

    resp = veiculo_client.post(f"/ui/rsd/veiculos/{item.id}/atualizar")

    assert resp.status_code == 400
    assert "não respondeu a tempo" in resp.text
    assert 'id="rsd-status-veiculo"' in resp.text

    inalterado = _veiculo_por_placa("TCM9G85")
    assert inalterado is not None
    assert inalterado.modelo == "Modelo Antigo"
    assert inalterado.marca == "MARCA ANTIGA"

    registro = _ultima_consulta(placa="TCM9G85")
    assert registro is not None
    assert registro.sucesso is False
    assert registro.veiculo_id == item.id


def test_ui_rsd_atualizar_veiculo_inexistente(
    veiculo_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login_ui(veiculo_client)
    _salvar_config_rsd(veiculo_client)
    _patch_client_from_config(monkeypatch)

    resp = veiculo_client.post("/ui/rsd/veiculos/999999/atualizar")

    assert resp.status_code == 404


def test_botao_atualizar_rsd_aparece_na_pagina_de_detalhes(
    veiculo_client: TestClient,
) -> None:
    _login_ui(veiculo_client)
    item = _veiculo_por_placa("TCM9G85")
    assert item is not None

    resp = veiculo_client.get(f"/ui/veiculos/{item.id}/detalhes")

    assert resp.status_code == 200
    assert f'hx-post="/ui/rsd/veiculos/{item.id}/atualizar"' in resp.text
    assert 'id="rsd-status-veiculo"' in resp.text
    assert "Atualizar dados" in resp.text


def test_pagina_da_rota_rsd_mapeia_para_veiculos() -> None:
    assert perfil.pagina_da_rota("/ui/rsd/veiculos/1/atualizar") == "veiculos"
    assert perfil.pagina_da_rota("/ui/rsd/puxar-dados") == "veiculos"
    assert perfil.pagina_da_rota("/ui/rsd/dossie/1/pdf") == "veiculos"
    assert perfil.pagina_da_rota("/consultas") == "veiculos"
    assert perfil.pagina_da_rota("/consultas/1/detalhe") == "veiculos"


# ---- Histórico de consultas (listagem, filtros e rotas) ----


def _seed_consultas(session: Session) -> int:
    """Cria um usuário e três consultas variando tipo/placa/sucesso/usuario.

    Devolve o id do usuário criado."""
    op = usuario.Usuario(username="rsd-hist", senha_hash="x", papel=usuario.Papel.admin)
    session.add(op)
    session.commit()

    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.puxar_dados,
        placa="TCM9G85",
        usuario_id=op.id,
        payload={"marca_modelo": "CHEV/ONIX"},
        campos_aplicados={"modelo": "ONIX"},
        sucesso=True,
    )
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.unitaria,
        placa="ABC1D23",
        usuario_id=op.id,
        dossie_id=351,
        status_dossie="done",
        sucesso=True,
    )
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.unitaria,
        placa="FAIL1",
        sucesso=False,
        erro="placa inválida",
    )
    return op.id


def test_listar_consultas_filtra_por_tipo(db_session: Session) -> None:
    _seed_consultas(db_session)

    puxar = rsd.listar_consultas(db_session, tipo=rsd.TipoConsultaRsd.puxar_dados)
    unitarias = rsd.listar_consultas(db_session, tipo=rsd.TipoConsultaRsd.unitaria)

    assert len(puxar) == 1
    assert puxar[0].placa == "TCM9G85"
    assert len(unitarias) == 2


def test_listar_consultas_filtra_por_placa_normaliza(db_session: Session) -> None:
    _seed_consultas(db_session)

    # "tcm-9g85" deve normalizar para "TCM9G85" e bater a linha
    rows = rsd.listar_consultas(db_session, placa="tcm-9g85")
    assert len(rows) == 1
    assert rows[0].placa == "TCM9G85"


def test_listar_consultas_filtra_por_usuario_e_sucesso(
    db_session: Session,
) -> None:
    op_id = _seed_consultas(db_session)

    do_op = rsd.listar_consultas(db_session, usuario_id=op_id)
    sem_op = rsd.listar_consultas(db_session, usuario_id=999_999)
    erros = rsd.listar_consultas(db_session, sucesso=False)
    ok = rsd.listar_consultas(db_session, sucesso=True)

    assert len(do_op) == 2
    assert sem_op == []
    assert len(erros) == 1
    assert erros[0].erro == "placa inválida"
    assert len(ok) == 2


def test_count_consultas_bate_com_listagem_sem_paginacao(
    db_session: Session,
) -> None:
    _seed_consultas(db_session)

    total = rsd.count_consultas(
        db_session, tipo=rsd.TipoConsultaRsd.unitaria, sucesso=True
    )
    rows = rsd.listar_consultas(
        db_session, tipo=rsd.TipoConsultaRsd.unitaria, sucesso=True, limit=1000
    )

    assert total == len(rows) == 1


def test_listar_consultas_ordena_mais_recente_primeiro(
    db_session: Session,
) -> None:
    _seed_consultas(db_session)

    rows = rsd.listar_consultas(db_session, limit=100)
    criados = [r.criado_em for r in rows if r.criado_em is not None]
    assert criados == sorted(criados, reverse=True)


def test_get_consulta_retorna_registro(db_session: Session) -> None:
    _seed_consultas(db_session)
    primeiro = rsd.listar_consultas(db_session, limit=1)[0]

    assert rsd.get_consulta(db_session, primeiro.id) is not None
    assert rsd.get_consulta(db_session, 999_999) is None


@pytest.fixture
def historico_client(make_client: Callable[..., TestClient]) -> TestClient:
    def _seed(session: Session) -> None:
        op = usuario.Usuario(
            username="rsd-hist", senha_hash="x", papel=usuario.Papel.admin
        )
        session.add(op)
        session.flush()
        # `registrar_consulta` abre sessão própria; commitamos para ele enxergar.
        session.commit()
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.puxar_dados,
            placa="TCM9G85",
            usuario_id=op.id,
            payload={"marca_modelo": "CHEV/ONIX"},
            campos_aplicados={"modelo": "ONIX"},
            sucesso=True,
        )
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.unitaria,
            placa="ABC1D23",
            usuario_id=op.id,
            dossie_id=351,
            status_dossie="done",
            sucesso=True,
        )
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.unitaria,
            placa="FAIL1",
            sucesso=False,
            erro="placa inválida",
        )

    return make_client(usuarios=[("admin", usuario.Papel.admin)], seed=_seed)


def test_ui_rsd_consultas_admin_retorna_200(historico_client: TestClient) -> None:
    _login_ui(historico_client)
    resp = historico_client.get("/consultas")
    assert resp.status_code == 200
    assert "Consultas" in resp.text
    assert "TCM9G85" in resp.text
    assert "ABC1D23" in resp.text


def test_ui_rsd_consultas_nao_admin_retorna_403(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(usuarios=[("func", usuario.Papel.funcionario)])
    resp = client.post(
        "/ui/login",
        data={"username": "func", "password": "senha"},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)
    resp = client.get("/consultas")
    assert resp.status_code == 403


def test_ui_rsd_consultas_detalhe_contem_payload(
    historico_client: TestClient,
) -> None:
    _login_ui(historico_client)

    listagem = historico_client.get("/consultas")
    assert listagem.status_code == 200

    # Pega o id da primeira linha de detalhe disponível
    match = re.search(r"/consultas/(\d+)/detalhe", listagem.text)
    assert match is not None
    consulta_id = int(match.group(1))

    resp = historico_client.get(f"/consultas/{consulta_id}/detalhe")
    assert resp.status_code == 200
    assert "Payload do portal" in resp.text
    assert "Campos aplicados" in resp.text


# ---- Indisponibilidade do motor do portal (502 upstream) ----


def _motor_502_response(status: int = 409) -> httpx.Response:
    """Resposta real do portal quando o backend dele falha."""
    return httpx.Response(
        status, json={"erro": "puxar_dados_atpv: motor respondeu 502"}
    )


def _client_com_handler(
    handler: Callable[[httpx.Request], httpx.Response],
) -> rsd.RsdClient:
    client = rsd.RsdClient(
        base_url="https://rsd.test",
        email="loja@test.com",
        senha="segredo",
    )
    client._client = httpx.Client(  # noqa: SLF001
        base_url="https://rsd.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=False,
    )
    return client


@pytest.fixture
def _sem_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mantém a quantidade de tentativas, zera a espera entre elas."""
    monkeypatch.setattr(rsd, "_RETRY_BACKOFF_S", (0.0, 0.0))


@pytest.mark.usefixtures("_sem_backoff")
def test_puxar_dados_retenta_quando_motor_do_portal_falha() -> None:
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            chamadas += 1
            if chamadas < 3:
                return _motor_502_response()
            return httpx.Response(200, json={"marca_modelo": "CHEV/ONIX"})
        return _handler(request)

    client = _client_com_handler(handler)
    with client:
        client.login()
        dados = client.puxar_dados("TCM9G85")

    assert chamadas == 3
    assert dados.marca_modelo == "CHEV/ONIX"


@pytest.mark.usefixtures("_sem_backoff")
def test_puxar_dados_motor_indisponivel_esgota_tentativas() -> None:
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            chamadas += 1
            return _motor_502_response()
        return _handler(request)

    client = _client_com_handler(handler)
    with client:
        client.login()
        with pytest.raises(rsd.RsdIndisponivelError) as excinfo:
            client.puxar_dados("TCM9G85")

    assert chamadas == len(rsd._RETRY_BACKOFF_S) + 1  # noqa: SLF001
    erro = excinfo.value
    # A mensagem da UI não repassa o texto interno do portal…
    assert "temporariamente indisponível" in str(erro)
    assert "motor respondeu" not in str(erro)
    # …mas ele fica disponível para log e histórico.
    assert erro.status_portal == 409
    assert erro.detalhe_portal == "puxar_dados_atpv: motor respondeu 502"


@pytest.mark.usefixtures("_sem_backoff")
def test_puxar_dados_nao_retenta_erro_de_negocio_do_portal() -> None:
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            chamadas += 1
            return httpx.Response(422, json={"erro": "placa inválida"})
        return _handler(request)

    client = _client_com_handler(handler)
    with client:
        client.login()
        with pytest.raises(rsd.RsdConsultaError, match="placa inválida"):
            client.puxar_dados("FAI1L23")

    assert chamadas == 1


@pytest.mark.usefixtures("_sem_backoff")
def test_puxar_dados_trata_5xx_direto_do_portal_como_indisponibilidade() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/atpv/puxar-dados/":
            return httpx.Response(502, text="Bad Gateway")
        return _handler(request)

    client = _client_com_handler(handler)
    with client:
        client.login()
        with pytest.raises(rsd.RsdIndisponivelError):
            client.puxar_dados("TCM9G85")


def test_testar_conexao_nao_confunde_portal_fora_do_ar_com_falta_de_permissao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/atpv/nova/":
            return httpx.Response(503, text="Service Unavailable")
        return _handler(request)

    client = _client_com_handler(handler)
    with client, pytest.raises(rsd.RsdIndisponivelError):
        client.testar_conexao()


def test_erro_para_historico_preserva_texto_cru_do_portal() -> None:
    erro = rsd.RsdIndisponivelError(
        "O portal RSD está temporariamente indisponível para consultas.",
        status_portal=409,
        detalhe_portal="puxar_dados_atpv: motor respondeu 502",
    )
    historico = rsd.erro_para_historico(erro)
    assert "motor respondeu 502" in historico
    assert rsd.contexto_log(erro)["status_portal"] == 409
    assert rsd.contexto_log(erro)["erro_tipo"] == "RsdIndisponivelError"


def test_erro_sem_detalhe_do_portal_nao_polui_historico() -> None:
    assert rsd.erro_para_historico(rsd.RsdConsultaError("placa inválida")) == (
        "placa inválida"
    )


def test_indisponibilidade_do_portal_nao_invalida_credencial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Portal fora do ar não diz nada sobre e-mail/senha.

    Antes, qualquer RsdError rebaixava a credencial para `failed` e o
    operador era mandado reconfigurar uma credencial correta.
    """
    testes: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rsd, "registrar_teste_config_persistente", lambda **kw: testes.append(kw)
    )

    class _PortalForaDoAr:
        def puxar_dados(self, _placa: str) -> rsd.PuxarDadosResult:
            raise rsd.RsdIndisponivelError(
                "O portal RSD está temporariamente indisponível para consultas.",
                status_portal=409,
                detalhe_portal="puxar_dados_atpv: motor respondeu 502",
            )

    _login_ui(client)
    _salvar_config_rsd(client)
    monkeypatch.setattr(rsd, "client_from_config", lambda _config: _PortalForaDoAr())

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "TCM9G85"})

    assert resp.status_code == 400
    assert testes == []
    assert "temporariamente indisponível" in resp.text
    assert "motor respondeu" not in resp.text


def test_falha_de_autenticacao_continua_invalidando_credencial(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    testes: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rsd, "registrar_teste_config_persistente", lambda **kw: testes.append(kw)
    )

    class _CredencialRejeitada:
        def puxar_dados(self, _placa: str) -> rsd.PuxarDadosResult:
            raise rsd.RsdAuthError("E-mail ou senha inválidos no portal RSD.")

    _login_ui(client)
    _salvar_config_rsd(client)
    monkeypatch.setattr(
        rsd, "client_from_config", lambda _config: _CredencialRejeitada()
    )

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "TCM9G85"})

    assert resp.status_code == 400
    assert len(testes) == 1
    assert testes[0]["sucesso"] is False
