"""Notificação de venda via bot do Telegram: config, formatação e envio.

Só notifica vendas de veículos cujo Investidor está marcado com
``notificar_telegram``. Espelha o fluxo de ``xtreme_system.whatsapp``.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import structlog
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base, register_post_commit
from xtreme_system.venda.core import Venda

logger = structlog.get_logger(__name__)

_CONFIG_ID = 1
_API_BASE_URL = "https://api.telegram.org"
_NOTIFICACAO_MAX_WORKERS = 2
_NOTIFICACAO_EXECUTOR = ThreadPoolExecutor(
    max_workers=_NOTIFICACAO_MAX_WORKERS,
    thread_name_prefix="telegram-notify",
)

MENSAGEM_TESTE = (
    "✅ Teste de integração do Xtreme System.\n"
    "Se você está lendo isto, as notificações de venda chegarão neste chat."
)

MENSAGEM_TEMPLATE_PADRAO = (
    "🚗 Venda registrada!\n"
    "Investidor: {investidor}\n"
    "Cliente: {cliente}\n"
    "Veículo: {veiculo}\n"
    "Valor: R$ {valor}\n"
    "Forma de pagamento: {forma_pagamento} ({parcelas}x)\n"
    "Vendedor: {vendedor}"
)


class TelegramConfig(Base):
    __tablename__ = "telegram_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_token: Mapped[str] = mapped_column(default="", server_default="")
    chat_id: Mapped[str] = mapped_column(default="", server_default="")
    mensagem_template: Mapped[str] = mapped_column(
        default=MENSAGEM_TEMPLATE_PADRAO,
        server_default=MENSAGEM_TEMPLATE_PADRAO,
    )


class TelegramConfigUpdate(BaseModel):
    bot_token: str = ""
    chat_id: str = ""
    mensagem_template: str = MENSAGEM_TEMPLATE_PADRAO


def get_config(session: Session) -> TelegramConfig:
    config = session.get(TelegramConfig, _CONFIG_ID)
    if config is None:
        config = TelegramConfig(id=_CONFIG_ID)
        session.add(config)
        crud.flush(session)
        session.refresh(config)
    return config


def atualizar_config(
    session: Session, data: TelegramConfigUpdate, actor_id: int | None = None
) -> TelegramConfig:
    config = get_config(session)
    antes = snapshot(config)
    config.bot_token = data.bot_token
    config.chat_id = data.chat_id
    config.mensagem_template = data.mensagem_template
    session.flush()
    session.refresh(config)
    auditar(
        session,
        actor_id=actor_id,
        tabela="telegram_config",
        tipo_acao="UPDATE",
        registro_id=config.id,
        dados_antes=antes,
        dados_depois=snapshot(config),
    )
    crud.flush(session)
    return config


class _PlaceholderDict(dict[str, object]):
    """Preserva `{chave}` no texto em vez de estourar KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _formatar_mensagem(config: TelegramConfig, venda_obj: Venda) -> str:
    vendedor = venda_obj.vendedor.username if venda_obj.vendedor else "-"
    dados = _PlaceholderDict(
        investidor=venda_obj.veiculo.investidor.nome,
        cliente=venda_obj.cliente.nome,
        veiculo=f"{venda_obj.veiculo.modelo} - placa {venda_obj.veiculo.placa}",
        valor=venda_obj.valor_venda,
        forma_pagamento=venda_obj.forma_pagamento,
        parcelas=venda_obj.parcelas,
        vendedor=vendedor,
    )
    template = config.mensagem_template or MENSAGEM_TEMPLATE_PADRAO
    return template.format_map(dados)


def _enviar(config: TelegramConfig, texto: str) -> None:
    # Bot API: POST /bot<token>/sendMessage, body JSON {chat_id, text}.
    # O token vai na URL — nunca logar a URL montada aqui.
    token = urllib.parse.quote(config.bot_token, safe="")
    url = f"{_API_BASE_URL}/bot{token}/sendMessage"
    payload = {"chat_id": config.chat_id, "text": texto}
    req = urllib.request.Request(  # noqa: S310 -- URL fixa da Bot API, não vem de input de usuário
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        resp.read()


def _descricao_erro_http(exc: urllib.error.HTTPError) -> str:
    """Extrai o campo `description` do corpo de erro da Bot API."""
    try:
        corpo = json.loads(exc.read().decode())
    except (ValueError, OSError, UnicodeDecodeError):
        return f"HTTP {exc.code}"
    descricao = corpo.get("description")
    return str(descricao) if descricao else f"HTTP {exc.code}"


def _dica_erro(codigo: int, descricao: str) -> str:
    """Traduz o erro da Bot API para uma ação concreta do admin."""
    texto = descricao.lower()
    if codigo in (401, 404):
        return "Token do bot inválido ou revogado. Gere um novo com o @BotFather."
    if "chat not found" in texto:
        return (
            "Chat não encontrado. Confira o ID (grupos começam com '-') e se o "
            "bot foi adicionado ao grupo."
        )
    if codigo == 403:
        return (
            "O bot não tem permissão para escrever neste chat. "
            "Adicione-o ao grupo (ou torne-o administrador, se for canal)."
        )
    return descricao


def enviar_teste(bot_token: str, chat_id: str) -> str | None:
    """Envia uma mensagem de teste síncrona. Retorna None se deu certo.

    Usado pelo botão "Testar envio" da tela de Configurações, então roda na
    thread da requisição e devolve o erro já traduzido para o admin, em vez
    de apenas logar como o caminho de notificação de venda faz.
    """
    if not bot_token:
        return "Preencha o token do bot antes de testar."
    if not chat_id:
        return "Preencha o ID do chat antes de testar."
    config = TelegramConfig(id=0, bot_token=bot_token, chat_id=chat_id)
    try:
        _enviar(config, MENSAGEM_TESTE)
    except urllib.error.HTTPError as exc:
        descricao = _descricao_erro_http(exc)
        logger.warning("telegram_teste_falhou", codigo=exc.code, descricao=descricao)
        return _dica_erro(exc.code, descricao)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        logger.warning("telegram_teste_falhou", error=str(exc))
        return f"Não foi possível contatar a API do Telegram: {exc}"
    logger.info("telegram_teste_enviado")
    return None


def _notificar_em_background(
    bot_token: str,
    chat_id: str,
    texto: str,
    venda_id: int,
    request_id: str | None,
) -> None:
    """Executada em thread separada — apenas o HTTP, sem acesso a banco."""
    config = TelegramConfig(id=0, bot_token=bot_token, chat_id=chat_id)
    log = logger.bind(venda_id=venda_id, request_id=request_id)
    try:
        _enviar(config, texto)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        log.warning("telegram_notify_failed", error=str(exc))
    except Exception:
        log.exception("telegram_notify_error")
    else:
        log.info("telegram_notify_sent")


def notificar_venda(
    session: Session, venda_obj: Venda, _actor_id: int | None = None
) -> None:
    """Agenda a notificação da venda para depois do commit, best-effort.

    Só envia se a integração estiver configurada (página de Configurações) e
    se o Investidor dono do veículo estiver marcado com `notificar_telegram`.
    A leitura do banco e a formatação da mensagem rodam na thread da
    requisição; o envio HTTP só é despachado (em thread separada) após o
    commit bem-sucedido. Se o commit falhar, nada é enviado. Uma falha de rede
    não impede a criação da venda.
    """
    config = get_config(session)
    if not (config.bot_token and config.chat_id):
        return
    if not venda_obj.veiculo.investidor.notificar_telegram:
        return
    texto = _formatar_mensagem(config, venda_obj)
    bot_token = config.bot_token
    chat_id = config.chat_id
    venda_id = venda_obj.id
    request_id = structlog.contextvars.get_contextvars().get("request_id")

    def _agendar_envio() -> None:
        _NOTIFICACAO_EXECUTOR.submit(
            _notificar_em_background,
            bot_token,
            chat_id,
            texto,
            venda_id,
            request_id,
        )

    register_post_commit(
        session,
        _agendar_envio,
    )
