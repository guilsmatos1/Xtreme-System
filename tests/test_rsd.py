"""Integração RSD: client HTTP (MockTransport) e rotas UI."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import Auditoria
from xtreme_system.database.core import SessionLocal
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
            "uf": "SP",
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
    assert mapped["modelo"] == "ONIX 10MT LT2"
    assert mapped["marca"] == "CHEV"
    assert mapped["cor"] == "CINZA"
    assert mapped["chassi"] == "9BGEB48A0SG190437"
    assert mapped["proprietario_documento"] == "44237309000175"
    assert mapped["proprietario_uf"] == "SP"


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
            rsd_client.puxar_dados("FAIL1")


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


def test_atualizar_config_criptografa_senha_em_repouso(db_session: Session) -> None:
    config = rsd.atualizar_config(
        db_session, rsd.RsdConfigUpdate(email="a@b.com", senha="segredo123")
    )
    assert config.senha != "segredo123"

    client = rsd.client_from_config(config)
    assert client.senha == "segredo123"


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
    assert "ONIX 10MT LT2" in resp.text
    assert "CHEV/ONIX 10MT LT2" not in resp.text


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
    assert '"vei_modelo": "ONIX 10MT LT2"' in resp.text


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

    resp = client.post("/ui/rsd/puxar-dados", data={"placa": "FAIL1"})
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


def test_pagina_da_rota_rsd_mapeia_para_veiculos() -> None:
    assert perfil.pagina_da_rota("/ui/rsd/puxar-dados") == "veiculos"
    assert perfil.pagina_da_rota("/ui/rsd/dossie/1/pdf") == "veiculos"
    assert perfil.pagina_da_rota("/ui/rsd/consultas") == "veiculos"
    assert perfil.pagina_da_rota("/ui/rsd/consultas/1/detalhe") == "veiculos"


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
    resp = historico_client.get("/ui/rsd/consultas")
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
    resp = client.get("/ui/rsd/consultas")
    assert resp.status_code == 403


def test_ui_rsd_consultas_detalhe_contem_payload(
    historico_client: TestClient,
) -> None:
    _login_ui(historico_client)

    listagem = historico_client.get("/ui/rsd/consultas")
    assert listagem.status_code == 200

    # Pega o id da primeira linha de detalhe disponível
    match = re.search(r"/ui/rsd/consultas/(\d+)/detalhe", listagem.text)
    assert match is not None
    consulta_id = int(match.group(1))

    resp = historico_client.get(f"/ui/rsd/consultas/{consulta_id}/detalhe")
    assert resp.status_code == 200
    assert "Payload do portal" in resp.text
    assert "Campos aplicados" in resp.text
