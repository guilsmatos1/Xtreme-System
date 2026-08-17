"""Notificação de venda via Telegram: filtrada por Investidor, best-effort."""

import io
import threading
import time
import urllib.error
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from xtreme_system.telegram import core as telegram
from xtreme_system.usuario import core as usuario

_TOKEN_SALVO = "111:salvo"  # noqa: S105 -- valor fake de teste
_TOKEN_NOVO = "222:novo"  # noqa: S105 -- valor fake de teste


def test_notificacao_em_background_loga_correlacao_e_erros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = MagicMock()
    logger = MagicMock()
    logger.bind.return_value = log
    monkeypatch.setattr(telegram, "logger", logger)

    monkeypatch.setattr(telegram, "_enviar", lambda _config, _texto: None)
    telegram._notificar_em_background(  # noqa: SLF001
        "token-do-bot",
        "-1001234567890",
        "texto",
        4312,
        "req-test-123",
    )

    logger.bind.assert_called_once_with(venda_id=4312, request_id="req-test-123")
    log.info.assert_called_once_with("telegram_notify_sent")

    log.reset_mock()

    def _falha_inesperada(_config: telegram.TelegramConfig, _texto: str) -> None:
        raise RuntimeError("configuração inválida")

    monkeypatch.setattr(telegram, "_enviar", _falha_inesperada)
    telegram._notificar_em_background(  # noqa: SLF001
        "token-do-bot",
        "-1001234567890",
        "texto",
        4312,
        "req-test-123",
    )

    log.exception.assert_called_once_with("telegram_notify_error")


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[("admin", usuario.Papel.admin)], invoke_post_commit=True
    )


def _token(client: TestClient, username: str) -> str:
    resp = client.post("/login", data={"username": username, "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def _seed(
    client: TestClient,
    headers: dict[str, str],
    *,
    notificar_telegram: bool = True,
    investidor_nome: str = "Ana",
    placa: str = "ABC1D23",
    documento: str = "12345678901",
) -> tuple[int, int]:
    inv_id = client.post(
        "/investidores",
        json={"nome": investidor_nome, "notificar_telegram": notificar_telegram},
        headers=headers,
    ).json()["id"]
    cliente_id = client.post(
        "/clientes",
        json={
            "nome": "João Silva",
            "documento": documento,
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
            "placa": placa,
            "km": 50000,
            "preco": "40000.00",
            "investidor_id": inv_id,
        },
        headers=headers,
    ).json()["id"]
    return cliente_id, veiculo_id


def _payload(cliente_id: int, veiculo_id: int) -> dict[str, Any]:
    return {
        "cliente_id": cliente_id,
        "veiculo_id": veiculo_id,
        "data_venda": "2026-07-01",
        "valor_venda": "40000.00",
        "forma_pagamento": "a_vista",
        "parcelas": 1,
    }


def _configurar(
    client: TestClient,
    mensagem_template: str = "",
    *,
    bot_token: str = "123456:token-do-bot",  # noqa: S107 -- valor fake de teste
    chat_id: str = "-1001234567890",
) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})
    client.post(
        "/ui/configuracoes/telegram",
        data={
            "bot_token": bot_token,
            "chat_id": chat_id,
            "telegram_mensagem_template": mensagem_template,
        },
    )


def _coletor(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[str], threading.Event]:
    mensagens: list[str] = []
    envio_concluido = threading.Event()

    def _enviar(_config: telegram.TelegramConfig, texto: str) -> None:
        mensagens.append(texto)
        envio_concluido.set()

    monkeypatch.setattr(telegram, "_enviar", _enviar)
    return mensagens, envio_concluido


def test_criar_venda_de_investidor_marcado_dispara_notificacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert envio_concluido.wait(timeout=1)
    assert len(mensagens) == 1
    assert "Ana" in mensagens[0]
    assert "JOÃO SILVA" in mensagens[0]
    assert "Gol" in mensagens[0]


def test_investidor_sem_flag_nao_dispara_notificacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso central: só investidores marcados geram mensagem."""
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=False)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert not envio_concluido.wait(timeout=0.3)
    assert mensagens == []


def test_apenas_vendas_do_investidor_marcado_notificam(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_marcado = _seed(
        client, headers, notificar_telegram=True, investidor_nome="Ana"
    )
    _, veiculo_ignorado = _seed(
        client,
        headers,
        notificar_telegram=False,
        investidor_nome="Bruno",
        placa="XYZ9K88",
        documento="98765432100",
    )

    assert (
        client.post(
            "/vendas", json=_payload(cliente_id, veiculo_ignorado), headers=headers
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/vendas", json=_payload(cliente_id, veiculo_marcado), headers=headers
        ).status_code
        == 201
    )

    assert envio_concluido.wait(timeout=1)
    assert len(mensagens) == 1
    assert "Ana" in mensagens[0]
    assert "Bruno" not in mensagens[0]


def test_criar_venda_pela_ui_htmx_dispara_notificacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A UI HTMX é o caminho real do dia a dia, não só a API JSON."""
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/ui/vendas",
        data={
            "cliente_id": str(cliente_id),
            "veiculo_id": str(veiculo_id),
            "data_venda": "2026-07-01",
            "valor_venda": "40000.00",
            "forma_pagamento": "a_vista",
            "parcelas": "1",
            "status": "pendente",
        },
    )

    assert resp.status_code == 200
    assert envio_concluido.wait(timeout=1)
    assert len(mensagens) == 1
    assert "Ana" in mensagens[0]


def test_sem_configuracao_nao_dispara_notificacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens, envio_concluido = _coletor(monkeypatch)
    client.post("/ui/login", data={"username": "admin", "password": "senha"})

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert not envio_concluido.wait(timeout=0.3)
    assert mensagens == []


def test_chat_id_vazio_nao_dispara_notificacao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(client, chat_id="")

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert not envio_concluido.wait(timeout=0.3)
    assert mensagens == []


def test_criar_venda_agenda_notificacao_em_executor_limitado(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens: list[str] = []
    submits: list[tuple[Callable[..., None], tuple[Any, ...]]] = []

    class _Executor:
        def submit(self, fn: Callable[..., None], *args: Any) -> None:
            submits.append((fn, args))
            fn(*args)

    monkeypatch.setattr(telegram, "_NOTIFICACAO_EXECUTOR", _Executor())
    monkeypatch.setattr(
        telegram, "_enviar", lambda _config, texto: mensagens.append(texto)
    )
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert len(submits) == 1
    assert callable(submits[0][0])
    assert len(mensagens) == 1


def test_falha_no_envio_nao_impede_criacao_da_venda(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _falha(_config: telegram.TelegramConfig, _texto: str) -> None:
        raise OSError("api.telegram.org inacessível")

    monkeypatch.setattr(telegram, "_enviar", _falha)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201


def test_envio_lento_nao_bloqueia_criacao_da_venda(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    envio_iniciado = threading.Event()
    liberar_envio = threading.Event()

    def _envio_lento(_config: telegram.TelegramConfig, _texto: str) -> None:
        envio_iniciado.set()
        liberar_envio.wait(timeout=2)

    monkeypatch.setattr(telegram, "_enviar", _envio_lento)
    _configurar(client)

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    inicio = time.perf_counter()
    try:
        resp = client.post(
            "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
        )
        duracao = time.perf_counter() - inicio

        assert resp.status_code == 201
        assert duracao < 1
        assert envio_iniciado.wait(timeout=1)
    finally:
        liberar_envio.set()


def test_configuracoes_telegram_salva_e_recarrega(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})

    resp = client.post(
        "/ui/configuracoes/telegram",
        data={
            "bot_token": "123456:token-secreto",
            "chat_id": "-1001234567890",
            "telegram_mensagem_template": "",
        },
    )
    assert resp.status_code == 200
    assert "-1001234567890" in resp.text
    assert 'class="alert alert--success"' in resp.text
    # O token é segredo: nunca volta para o formulário.
    assert "123456:token-secreto" not in resp.text

    resp = client.get("/ui/configuracoes?aba=telegram")
    assert resp.status_code == 200
    assert "-1001234567890" in resp.text
    assert "123456:token-secreto" not in resp.text
    # O botão de teste e seu alvo HTMX precisam existir na página.
    assert "/ui/configuracoes/telegram/teste" in resp.text
    assert 'id="telegram-test-result"' in resp.text
    assert "Testar envio" in resp.text
    assert 'name="csrf_token"' in resp.text


def test_configuracoes_telegram_token_vazio_mantem_o_atual(
    client: TestClient,
) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})
    client.post(
        "/ui/configuracoes/telegram",
        data={"bot_token": "123456:token", "chat_id": "-100111"},
    )

    resp = client.post(
        "/ui/configuracoes/telegram",
        data={"bot_token": "", "chat_id": "-100222"},
    )

    assert resp.status_code == 200
    assert "-100222" in resp.text
    assert "Conectado" in resp.text


def test_notificacao_usa_template_customizado(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(
        client,
        mensagem_template="Venda de {investidor} para {cliente} por R$ {valor}",
    )

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert envio_concluido.wait(timeout=1)
    assert mensagens == ["Venda de Ana para JOÃO SILVA por R$ 40000.00"]


def test_notificacao_ignora_placeholder_desconhecido(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mensagens, envio_concluido = _coletor(monkeypatch)
    _configurar(client, mensagem_template="Olá {cliente}, código {inexistente}")

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    cliente_id, veiculo_id = _seed(client, headers, notificar_telegram=True)

    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    assert envio_concluido.wait(timeout=1)
    assert mensagens == ["Olá JOÃO SILVA, código {inexistente}"]


def _csrf_headers(client: TestClient) -> dict[str, str]:
    client.get("/ui/configuracoes?aba=telegram")
    return {"X-CSRFToken": client.cookies["csrf_token"]}


def test_botao_teste_envia_mensagem_e_reporta_sucesso(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enviadas: list[str] = []
    monkeypatch.setattr(
        telegram, "_enviar", lambda _config, texto: enviadas.append(texto)
    )
    _configurar(client)

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": "", "chat_id": ""},
        headers={"HX-Request": "true", **_csrf_headers(client)},
    )

    assert resp.status_code == 200
    assert enviadas == [telegram.MENSAGEM_TESTE]
    assert "rsd-test-result--success" in resp.text


def test_botao_teste_usa_valores_do_formulario_ainda_nao_salvos(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    usados: list[tuple[str, str]] = []

    def _enviar(config: telegram.TelegramConfig, _texto: str) -> None:
        usados.append((config.bot_token, config.chat_id))

    monkeypatch.setattr(telegram, "_enviar", _enviar)
    _configurar(client, bot_token=_TOKEN_SALVO, chat_id="-100salvo")

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": _TOKEN_NOVO, "chat_id": "-100novo"},
        headers={"HX-Request": "true", **_csrf_headers(client)},
    )

    assert resp.status_code == 200
    assert usados == [(_TOKEN_NOVO, "-100novo")]


def test_botao_teste_com_token_em_branco_usa_o_token_salvo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O formulário nunca devolve o token, então em branco = manter o salvo."""
    usados: list[tuple[str, str]] = []

    def _enviar(config: telegram.TelegramConfig, _texto: str) -> None:
        usados.append((config.bot_token, config.chat_id))

    monkeypatch.setattr(telegram, "_enviar", _enviar)
    _configurar(client, bot_token=_TOKEN_SALVO, chat_id="-100salvo")

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": "", "chat_id": "-100novo"},
        headers={"HX-Request": "true", **_csrf_headers(client)},
    )

    assert resp.status_code == 200
    assert usados == [(_TOKEN_SALVO, "-100novo")]


def test_botao_teste_traduz_erro_da_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _falha(_config: telegram.TelegramConfig, _texto: str) -> None:
        raise urllib.error.HTTPError(
            "https://api.telegram.org",
            400,
            "Bad Request",
            {},  # type: ignore[arg-type]
            io.BytesIO(b'{"ok":false,"description":"Bad Request: chat not found"}'),
        )

    monkeypatch.setattr(telegram, "_enviar", _falha)
    _configurar(client)

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": "", "chat_id": "-100errado"},
        headers={"HX-Request": "true", **_csrf_headers(client)},
    )

    assert resp.status_code == 400
    assert "rsd-test-result--error" in resp.text
    assert "Chat não encontrado" in resp.text


def test_botao_teste_token_invalido_orienta_o_admin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _falha(_config: telegram.TelegramConfig, _texto: str) -> None:
        raise urllib.error.HTTPError(
            "https://api.telegram.org",
            401,
            "Unauthorized",
            {},  # type: ignore[arg-type]
            io.BytesIO(b'{"ok":false,"description":"Unauthorized"}'),
        )

    monkeypatch.setattr(telegram, "_enviar", _falha)
    _configurar(client)

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": "", "chat_id": ""},
        headers={"HX-Request": "true", **_csrf_headers(client)},
    )

    assert resp.status_code == 400
    assert "BotFather" in resp.text


def test_botao_teste_sem_configuracao_nao_chama_a_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr(
        telegram, "_enviar", lambda _config, texto: chamadas.append(texto)
    )
    client.post("/ui/login", data={"username": "admin", "password": "senha"})

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": "", "chat_id": ""},
        headers={"HX-Request": "true", **_csrf_headers(client)},
    )

    assert resp.status_code == 400
    assert chamadas == []
    assert "Preencha o token" in resp.text


def test_botao_teste_exige_csrf(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []
    monkeypatch.setattr(
        telegram, "_enviar", lambda _config, texto: chamadas.append(texto)
    )
    _configurar(client)

    resp = client.post(
        "/ui/configuracoes/telegram/teste",
        data={"bot_token": "", "chat_id": ""},
        headers={"HX-Request": "true"},
    )

    assert resp.status_code == 403
    assert chamadas == []


def test_auditoria_mascara_bot_token(client: TestClient) -> None:
    client.post("/ui/login", data={"username": "admin", "password": "senha"})
    client.post(
        "/ui/configuracoes/telegram",
        data={"bot_token": "123456:token-secreto", "chat_id": "-100111"},
    )

    headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    resp = client.get(
        "/auditoria", params={"tabela": "telegram_config", "limit": 1}, headers=headers
    )

    assert resp.status_code == 200
    assert "123456:token-secreto" not in resp.text
    assert "***" in resp.text
