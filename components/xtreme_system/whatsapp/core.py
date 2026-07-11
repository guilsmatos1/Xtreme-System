"""Notificação de venda via WhatsApp (Evolution API): config, formatação e envio."""

import json
import urllib.error
import urllib.request

import structlog
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.database.core import Base
from xtreme_system.venda.core import Venda

logger = structlog.get_logger(__name__)

_CONFIG_ID = 1


class WhatsappConfig(Base):
    __tablename__ = "whatsapp_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    evolution_api_url: Mapped[str] = mapped_column(default="")
    evolution_api_key: Mapped[str] = mapped_column(default="")
    evolution_instance: Mapped[str] = mapped_column(default="")
    evolution_group_id: Mapped[str] = mapped_column(default="")


class WhatsappConfigUpdate(BaseModel):
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    evolution_instance: str = ""
    evolution_group_id: str = ""


def get_config(session: Session) -> WhatsappConfig:
    config = session.get(WhatsappConfig, _CONFIG_ID)
    if config is None:
        config = WhatsappConfig(id=_CONFIG_ID)
        session.add(config)
        session.commit()
        session.refresh(config)
    return config


def atualizar_config(session: Session, data: WhatsappConfigUpdate) -> WhatsappConfig:
    config = get_config(session)
    config.evolution_api_url = data.evolution_api_url
    config.evolution_api_key = data.evolution_api_key
    config.evolution_instance = data.evolution_instance
    config.evolution_group_id = data.evolution_group_id
    session.commit()
    session.refresh(config)
    return config


def _formatar_mensagem(venda_obj: Venda) -> str:
    vendedor = venda_obj.vendedor.username if venda_obj.vendedor else "-"
    return (
        "🚗 Nova venda registrada!\n"
        f"Cliente: {venda_obj.cliente.nome}\n"
        f"Veículo: {venda_obj.veiculo.modelo} - placa {venda_obj.veiculo.placa}\n"
        f"Valor: R$ {venda_obj.valor_venda}\n"
        f"Forma de pagamento: {venda_obj.forma_pagamento} ({venda_obj.parcelas}x)\n"
        f"Vendedor: {vendedor}"
    )


def _enviar(config: WhatsappConfig, texto: str) -> None:
    # ponytail: payload assume o formato do endpoint sendText do Evolution API v2
    # (POST /message/sendText/{instance}, header apikey, body {number, text}).
    # Conferir contra a versão real da instância quando ela subir.
    url = f"{config.evolution_api_url}/message/sendText/{config.evolution_instance}"
    payload = {"number": config.evolution_group_id, "text": texto}
    req = urllib.request.Request(  # noqa: S310 -- url vem de config de admin, não de input de usuário
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": config.evolution_api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        resp.read()


def notificar_venda(session: Session, venda_obj: Venda) -> None:
    """Envia a notificação da venda para o grupo do WhatsApp, best-effort.

    Nunca propaga exceção: uma falha de rede/servidor Evolution não pode
    impedir a criação da venda. Se a integração ainda não foi configurada
    (página de Configurações), não tenta enviar.
    """
    config = get_config(session)
    if not (config.evolution_api_url and config.evolution_instance):
        return
    try:
        _enviar(config, _formatar_mensagem(venda_obj))
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        logger.warning("whatsapp_notify_failed", error=str(exc))
