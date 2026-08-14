"""Integração com o portal RSD (lojas.rsdsistema.com.br).

Autentica por sessão Django (cookie + CSRF). Não há API REST pública:
consulta unitária cria um dossiê e faz poll em /dossie/<id>/status/;
puxar dados usa POST /atpv/puxar-dados/ (JSON).
"""

# The RSD integration intentionally centralizes the HTTP lifecycle and cache
# coordination in this module. Keep these structural warnings local to this
# boundary; behavior-specific lint checks remain enabled.
# pylint: disable=protected-access,too-many-instance-attributes,too-many-lines,too-many-boolean-expressions

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import re
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from enum import StrEnum
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base, SessionLocal

logger = structlog.get_logger(__name__)

_CONFIG_ID = 1
_DEFAULT_BASE_HOST = "lojas.rsdsistema.com.br"
_DEFAULT_BASE_URL = f"https://{_DEFAULT_BASE_HOST}"
_ALLOWED_RSD_PORTS = frozenset({443})
_FERNET_TOKEN_PREFIX = "gAAAAA"  # noqa: S105 — marcador do formato Fernet


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rsd_encryption_key: str
    rsd_allowed_hosts: str = _DEFAULT_BASE_HOST

    @field_validator("rsd_encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 32:
            raise ValueError("RSD_ENCRYPTION_KEY deve ter pelo menos 32 caracteres")
        if len(set(normalized)) < 8:
            raise ValueError("RSD_ENCRYPTION_KEY não possui entropia suficiente")
        if normalized.lower() in {
            "your-rsd-encryption-key-change-this-in-production",
            "change-me",
            "changeme",
        } or normalized.lower().startswith(("your-", "change-")):
            raise ValueError("RSD_ENCRYPTION_KEY não pode usar um placeholder")
        auth_secret = os.environ.get("AUTH_SECRET_KEY", "").strip()
        if auth_secret and normalized == auth_secret:
            raise ValueError("RSD_ENCRYPTION_KEY deve ser diferente da chave de auth")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_startup_settings() -> None:
    """Fail startup before any RSD credential can be written or used."""
    get_settings()


@lru_cache
def _get_fernet() -> Fernet:
    return _fernet_for_secret(get_settings().rsd_encryption_key)


def _fernet_for_secret(secret: str) -> Fernet:
    # Chave arbitrária -> chave Fernet válida (32 bytes url-safe base64), para
    # não exigir que RSD_ENCRYPTION_KEY já venha nesse formato específico.
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encriptar_senha(senha: str) -> str:
    if not senha:
        return ""
    return _get_fernet().encrypt(senha.encode("utf-8")).decode("ascii")


def _decriptar_senha(valor: str) -> str:
    if not valor:
        return ""
    try:
        return _get_fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except (InvalidToken, TypeError, UnicodeError, ValueError) as exc:
        logger.warning("rsd_decriptar_senha_falhou_chave_invalida")
        raise RsdEncryptionError(
            "A senha RSD não pode ser decriptada. Verifique a chave de criptografia "
            "e solicite intervenção administrativa."
        ) from exc


_LOGIN_PATH = "/accounts/login/"
_UNITARIA_PATH = "/dossie/unitaria/"
_ATPV_NOVA_PATH = "/atpv/nova/"
_PUXAR_DADOS_PATH = "/atpv/puxar-dados/"
_CSRF_RE = re.compile(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"')
_DOSSIE_ID_RE = re.compile(r"/dossie/(\d+)/?")
_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 120.0
_POLL_MAX_ERROS_CONSECUTIVOS = 3
_HTTP_TIMEOUT_S = 30.0
_MSG_PORTAL_MAX_LEN = 300
# O portal embrulha falhas do backend dele ("motor") em respostas próprias,
# às vezes com status 4xx — só a mensagem revela que a origem é upstream.
_MOTOR_5XX_RE = re.compile(r"motor respondeu\s+(5\d\d)")
_STATUS_UPSTREAM = frozenset({500, 502, 503, 504})
_MSG_PORTAL_INDISPONIVEL = (
    "O portal RSD está temporariamente indisponível para consultas. "
    "Tente novamente em alguns minutos."
)
# Espera entre as tentativas; o total de tentativas é len(backoff) + 1.
_RETRY_BACKOFF_S = (1.0, 3.0)


class RsdError(Exception):
    """Erro genérico da integração RSD.

    `status_portal` e `detalhe_portal` preservam a resposta crua do RSD para
    log e histórico, sem que ela precise virar a mensagem mostrada ao
    operador.
    """

    def __init__(
        self,
        *args: object,
        status_portal: int | None = None,
        detalhe_portal: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.status_portal = status_portal
        self.detalhe_portal = detalhe_portal


class RsdNotConfiguredError(RsdError):
    """Credenciais RSD ainda não configuradas."""


class RsdEncryptionError(RsdError):
    """A credencial persistida não pode ser aberta com a chave atual."""


class RsdConfigError(RsdError):
    """A configuração do cliente RSD viola os limites de segurança."""


class RsdAuthError(RsdError):
    """Falha de login (credenciais ou CSRF)."""


class RsdCapabilityError(RsdError):
    """A conta autenticou, mas não pode usar uma capacidade RSD."""


class RsdClientRetiredError(RsdError):
    """O cliente cacheado foi invalidado durante uma troca de configuração."""


class RsdTimeoutError(RsdError):
    """Uma chamada ao portal RSD excedeu o tempo de espera."""


class RsdConsultaError(RsdError):
    """Portal retornou erro na consulta."""


class RsdIndisponivelError(RsdError):
    """O portal respondeu, mas o backend dele ("motor") falhou.

    Separado de `RsdConsultaError` porque não diz nada sobre a credencial nem
    sobre a placa consultada: é indisponibilidade momentânea do fornecedor.
    """


def _allowed_rsd_hosts() -> frozenset[str]:
    raw = os.environ.get("RSD_ALLOWED_HOSTS", _DEFAULT_BASE_HOST)
    hosts = frozenset(item.strip().lower() for item in raw.split(",") if item.strip())
    if not hosts:
        raise RsdConfigError("RSD_ALLOWED_HOSTS deve conter ao menos um host.")
    return hosts


def _validate_resolved_addresses(host: str, port: int) -> None:
    # `.test` é reservado para endpoints de teste e não é resolvível por DNS;
    # ele é permitido apenas quando explicitamente incluído na allowlist.
    if host.endswith(".test"):
        return
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RsdConfigError(
            "Não foi possível resolver o host permitido do portal RSD."
        ) from exc
    if not addresses:
        raise RsdConfigError("O host do portal RSD não possui endereço resolvido.")
    for _family, _socktype, _proto, _canonname, sockaddr in addresses:
        address = ipaddress.ip_address(sockaddr[0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise RsdConfigError(
                "O host do portal RSD resolve para um destino de rede não permitido."
            )


def _validate_rsd_url(value: str, *, redirect: bool = False) -> str:
    raw = (value or "").strip()
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError as exc:
        raise RsdConfigError("A URL base do RSD é inválida.") from exc
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme.lower() != "https":
        raise RsdConfigError("A URL do RSD deve usar HTTPS.")
    if not host or parts.username is not None or parts.password is not None:
        raise RsdConfigError("A URL do RSD não pode conter usuário ou senha.")
    if parts.fragment:
        raise RsdConfigError("A URL do RSD não pode conter fragmento.")
    if host not in _allowed_rsd_hosts():
        raise RsdConfigError("O host da URL do RSD não está na allowlist.")
    if _is_ip_literal(host):
        raise RsdConfigError("A URL do RSD não pode usar um IP literal.")
    if port is not None and port not in _ALLOWED_RSD_PORTS:
        raise RsdConfigError("A porta da URL do RSD não é permitida.")
    if not redirect and (parts.path not in {"", "/"} or parts.query):
        raise RsdConfigError("A URL base do RSD deve apontar para a raiz do portal.")
    _validate_resolved_addresses(host, port or 443)
    netloc = host if port in (None, 443) else f"{host}:{port}"
    path = parts.path.rstrip("/") if not redirect else parts.path or "/"
    return urlunsplit(("https", netloc, path, parts.query if redirect else "", ""))


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _validated_redirect(url: str, response: httpx.Response) -> str | None:
    if response.status_code not in {301, 302, 303, 307, 308}:
        return None
    location = response.headers.get("Location")
    if not location:
        raise RsdConsultaError("O portal RSD devolveu um redirecionamento inválido.")
    return _validate_rsd_url(urljoin(url, location), redirect=True)


class RsdConfig(Base):
    __tablename__ = "rsd_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(default="", server_default="")
    senha: Mapped[str] = mapped_column(default="", server_default="")
    base_url: Mapped[str] = mapped_column(
        default=_DEFAULT_BASE_URL, server_default=_DEFAULT_BASE_URL
    )
    revogada: Mapped[bool] = mapped_column(default=False, server_default="false")
    status: Mapped[str] = mapped_column(
        default="saved_unverified", server_default="saved_unverified"
    )
    ultimo_teste_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_teste_erro: Mapped[str | None] = mapped_column(Text)
    ultimo_teste_fingerprint: Mapped[str | None]


class RsdConfigUpdate(BaseModel):
    email: str = ""
    senha: str = ""
    base_url: str = _DEFAULT_BASE_URL
    teste_prova: str = ""


class RsdCredentialStatus(StrEnum):
    saved_unverified = "saved_unverified"
    verified = "verified"
    failed = "failed"


class TipoConsultaRsd(StrEnum):
    puxar_dados = "puxar_dados"
    unitaria = "unitaria"


class RsdConsulta(Base):
    """Registro de auditoria de cada chamada ao portal RSD, com o payload bruto."""

    __tablename__ = "rsd_consulta"
    __table_args__ = (Index("ix_rsd_consulta_placa_criado_em", "placa", "criado_em"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoConsultaRsd]
    placa: Mapped[str] = mapped_column(index=True)
    veiculo_id: Mapped[int | None] = mapped_column(
        ForeignKey("veiculo.id", ondelete="SET NULL"), index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    campos_aplicados: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sucesso: Mapped[bool] = mapped_column(default=True)
    erro: Mapped[str | None]
    dossie_id: Mapped[int | None] = mapped_column(index=True)
    status_dossie: Mapped[str | None]
    duracao_ms: Mapped[int | None]
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def _alias(*nomes: str) -> AliasChoices:
    """Aceita o campo sob qualquer um dos nomes que o portal já usou.

    O JSON de `puxar-dados` não tem contrato publicado e o portal varia a
    grafia entre consultas (com/sem acento, `numero_motor` vs `motor`).
    Declarar as variantes aqui evita perder o dado silenciosamente — o que
    não casar com nenhum alias continua visível em `model_extra`.
    """
    return AliasChoices(*nomes)


class PuxarDadosResult(BaseModel):
    # `extra="allow"` é deliberado: chaves ainda não mapeadas sobrevivem ao
    # `model_dump()` e ficam gravadas em `RsdConsulta.payload`, que é como
    # descobrimos a grafia real de um campo novo sem instrumentar o portal.
    model_config = {"extra": "allow", "populate_by_name": True}

    placa: str = ""
    renavam: str | None = None
    chassi: str | None = None
    marca_modelo: str | None = None
    ano: int | None = None
    cor: str | None = None
    nome_proprietario: str | None = None
    cpf_cnpj: str | None = None
    tipo_documento: str | None = None
    uf: str | None = None
    outro_estado: bool = False
    origem: str | None = None
    erro: str | None = None

    categoria: str | None = Field(
        default=None, validation_alias=_alias("categoria", "categoria_veiculo")
    )
    especie: str | None = Field(
        default=None,
        validation_alias=_alias("especie", "espécie", "especie_veiculo"),
    )
    combustivel: str | None = Field(
        default=None,
        validation_alias=_alias("combustivel", "combustível", "tipo_combustivel"),
    )
    potencia: str | None = Field(
        default=None, validation_alias=_alias("potencia", "potência", "potencia_cv")
    )
    cilindrada: str | None = Field(
        default=None, validation_alias=_alias("cilindrada", "cilindradas", "cc")
    )
    numero_motor: str | None = Field(
        default=None,
        validation_alias=_alias("numero_motor", "número_motor", "motor", "n_motor"),
    )
    procedencia: str | None = Field(
        default=None, validation_alias=_alias("procedencia", "procedência")
    )
    municipio: str | None = Field(
        default=None,
        validation_alias=_alias("municipio", "município", "municipio_placa"),
    )
    proprietario_anterior: str | None = Field(
        default=None,
        validation_alias=_alias(
            "proprietario_anterior",
            "proprietário_anterior",
            "nome_proprietario_anterior",
        ),
    )

    @field_validator("potencia", "cilindrada", "numero_motor", "renavam", mode="before")
    @classmethod
    def _numero_como_texto(cls, value: Any) -> Any:
        """O portal manda potência/cilindrada ora como número, ora como string.

        São colunas de texto no `Veiculo` (guardam "1.0", "999 cc"), então
        normalizamos aqui — o pydantic v2 não coage int→str sozinho e a
        consulta inteira falharia com ValidationError.
        """
        _ = cls
        return str(value) if isinstance(value, int | float) else value


class UnitariaResult(BaseModel):
    dossie_id: int
    status: str
    status_display: str | None = None
    error: str | None = None
    portais: list[dict[str, Any]] = Field(default_factory=list)
    has_consolidado: bool = False
    is_terminal: bool = True


def get_config(session: Session) -> RsdConfig:
    config = session.get(RsdConfig, _CONFIG_ID)
    if config is None:
        config = RsdConfig(id=_CONFIG_ID)
        session.add(config)
        crud.flush(session)
        session.refresh(config)
    return config


def configurado(config: RsdConfig) -> bool:
    return bool(not config.revogada and config.email.strip() and config.senha)


def _credential_fingerprint(email: str, senha: str, base_url: str) -> str:
    base = base_url.strip().rstrip("/") or _DEFAULT_BASE_URL
    material = "\x00".join((email.strip(), senha, base))
    return hmac.new(
        get_settings().rsd_encryption_key.encode("utf-8"),
        material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def credential_fingerprint(*, email: str, senha: str, base_url: str) -> str:
    """Fingerprint opaco usado para vincular um teste ao mesmo rascunho."""
    return _credential_fingerprint(email, senha, base_url)


def _emitir_teste_prova(*, fingerprint: str, testado_em: datetime) -> str:
    timestamp = str(int(testado_em.timestamp()))
    payload = f"{timestamp}.{fingerprint}"
    assinatura = hmac.new(
        get_settings().rsd_encryption_key.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{assinatura}"


def emitir_teste_prova(*, email: str, senha: str, base_url: str) -> str:
    """Cria uma prova assinada para o botão Salvar após teste aprovado."""
    return _emitir_teste_prova(
        fingerprint=_credential_fingerprint(email, senha, base_url),
        testado_em=datetime.now(UTC),
    )


def _validar_teste_prova(
    *, prova: str, fingerprint: str, agora: datetime
) -> datetime | None:
    try:
        timestamp, prova_fingerprint, assinatura = prova.split(".", 2)
        testado_em = datetime.fromtimestamp(int(timestamp), tz=UTC)
    except (ValueError, TypeError, OverflowError):
        return None
    payload = f"{timestamp}.{prova_fingerprint}"
    esperada = hmac.new(
        get_settings().rsd_encryption_key.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if (
        not hmac.compare_digest(prova_fingerprint, fingerprint)
        or not hmac.compare_digest(assinatura, esperada)
        or agora - testado_em > timedelta(minutes=10)
        or testado_em - agora > timedelta(minutes=1)
    ):
        return None
    return testado_em


def _erro_teste_sanitizado(erro: Exception) -> str:
    if isinstance(erro, RsdAuthError):
        return "Falha de autenticação: o portal rejeitou as credenciais informadas."
    if isinstance(erro, RsdTimeoutError):
        return "Falha de disponibilidade: o portal RSD não respondeu a tempo."
    if isinstance(erro, RsdIndisponivelError):
        return "Falha de disponibilidade: o portal RSD está fora do ar."
    return "Falha de disponibilidade: não foi possível verificar o portal RSD."


def mensagem_teste(erro: Exception) -> str:
    """Mensagem segura para a interface, sem detalhes do portal externo."""
    return _erro_teste_sanitizado(erro)


def contexto_log(erro: Exception) -> dict[str, Any]:
    """Campos de log que preservam a resposta crua do portal."""
    return {
        "erro": str(erro),
        "erro_tipo": type(erro).__name__,
        "status_portal": getattr(erro, "status_portal", None),
        "detalhe_portal": getattr(erro, "detalhe_portal", None),
    }


def erro_para_historico(erro: Exception) -> str:
    """Mensagem gravada em `rsd_consulta`, com o detalhe cru do portal.

    A interface mostra `str(erro)` (texto tratado); o histórico guarda também
    o que o portal respondeu, que é o que permite diagnosticar depois.
    """
    detalhe = getattr(erro, "detalhe_portal", None)
    return f"{erro} [portal: {detalhe}]" if detalhe else str(erro)


def senha_config(config: RsdConfig) -> str:
    """Obtém a senha ativa apenas para operações internas do fluxo de teste."""
    return _decriptar_senha(config.senha)


def status_config(config: RsdConfig) -> RsdCredentialStatus:
    if not configurado(config):
        return RsdCredentialStatus.saved_unverified
    try:
        return RsdCredentialStatus(
            config.status or RsdCredentialStatus.saved_unverified
        )
    except (TypeError, ValueError):
        return RsdCredentialStatus.saved_unverified


def atualizar_config(
    session: Session, data: RsdConfigUpdate, actor_id: int | None = None
) -> RsdConfig:
    config = get_config(session)
    base = _validate_rsd_url(data.base_url or _DEFAULT_BASE_URL)
    antes = snapshot(config)
    senha_anterior = _decriptar_senha(config.senha)
    fingerprint_anterior = _credential_fingerprint(
        config.email, senha_anterior, config.base_url or _DEFAULT_BASE_URL
    )
    email = data.email.strip()
    senha = data.senha or senha_anterior
    fingerprint = _credential_fingerprint(email, senha, base)
    testado_em = _validar_teste_prova(
        prova=data.teste_prova, fingerprint=fingerprint, agora=datetime.now(UTC)
    )
    mesma_credencial = (
        configurado(config)
        and hmac.compare_digest(fingerprint_anterior, fingerprint)
        and status_config(config) == RsdCredentialStatus.verified
    )
    config.email = email
    if data.senha:
        config.senha = _encriptar_senha(data.senha)
    config.base_url = base or _DEFAULT_BASE_URL
    config.revogada = False
    if testado_em is not None or mesma_credencial:
        config.status = RsdCredentialStatus.verified.value
        if testado_em is not None:
            config.ultimo_teste_em = testado_em
            config.ultimo_teste_erro = None
            config.ultimo_teste_fingerprint = fingerprint
    else:
        config.status = RsdCredentialStatus.saved_unverified.value
        config.ultimo_teste_em = None
        config.ultimo_teste_erro = None
        config.ultimo_teste_fingerprint = None
    session.flush()
    session.refresh(config)
    auditar(
        session,
        actor_id=actor_id,
        tabela="rsd_config",
        tipo_acao="UPDATE",
        registro_id=config.id,
        dados_antes=antes,
        dados_depois=snapshot(config),
    )
    crud.flush(session)
    invalidar_client_cache()
    return config


def registrar_teste_config(
    session: Session,
    *,
    email: str,
    senha: str,
    base_url: str,
    sucesso: bool,
    erro: Exception | None = None,
    testado_em: datetime | None = None,
) -> RsdConfig | None:
    """Atualiza o último teste somente quando ele corresponde à config ativa."""
    config = get_config(session)
    senha_ativa = _decriptar_senha(config.senha)
    fingerprint = _credential_fingerprint(email, senha, base_url)
    ativo = _credential_fingerprint(config.email, senha_ativa, config.base_url)
    if not configurado(config) or not hmac.compare_digest(fingerprint, ativo):
        return None
    config.status = (
        RsdCredentialStatus.verified.value
        if sucesso
        else RsdCredentialStatus.failed.value
    )
    config.ultimo_teste_em = testado_em or datetime.now(UTC)
    config.ultimo_teste_fingerprint = fingerprint
    config.ultimo_teste_erro = (
        None if sucesso or erro is None else _erro_teste_sanitizado(erro)
    )
    session.flush()
    return config


def registrar_teste_config_persistente(
    *,
    email: str,
    senha: str,
    base_url: str,
    sucesso: bool,
    erro: Exception | None = None,
    testado_em: datetime | None = None,
) -> None:
    """Persiste o resultado de um teste que já liberou a sessão do request."""
    session = SessionLocal()
    try:
        registrar_teste_config(
            session,
            email=email,
            senha=senha,
            base_url=base_url,
            sucesso=sucesso,
            erro=erro,
            testado_em=testado_em,
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("rsd_estado_teste_nao_persistido", exc_info=True)
    finally:
        session.close()


def revogar_config(session: Session, actor_id: int | None = None) -> RsdConfig:
    """Remove a credencial RSD e invalida qualquer sessão em memória."""
    config = get_config(session)
    antes = snapshot(config)
    config.email = ""
    config.senha = ""
    config.base_url = _DEFAULT_BASE_URL
    config.revogada = True
    session.flush()
    session.refresh(config)
    auditar(
        session,
        actor_id=actor_id,
        tabela="rsd_config",
        tipo_acao="REVOKE",
        registro_id=config.id,
        dados_antes=antes,
        dados_depois=snapshot(config),
    )
    crud.flush(session)
    invalidar_client_cache()
    return config


def recriptografar_config(
    session: Session, chave_anterior: str, actor_id: int | None = None
) -> RsdConfig:
    """Recifra a credencial com a chave atual dentro da transação do chamador."""
    config = get_config(session)
    if not config.senha:
        return config
    try:
        senha = _fernet_for_secret(chave_anterior).decrypt(config.senha.encode("ascii"))
        nova_senha = _get_fernet().encrypt(senha).decode("ascii")
    except (InvalidToken, TypeError, UnicodeError, ValueError) as exc:
        raise RsdEncryptionError(
            "A senha RSD não pode ser recifrada com a chave anterior fornecida."
        ) from exc
    antes = snapshot(config)
    config.senha = nova_senha
    session.flush()
    session.refresh(config)
    auditar(
        session,
        actor_id=actor_id,
        tabela="rsd_config",
        tipo_acao="UPDATE",
        registro_id=config.id,
        dados_antes=antes,
        dados_depois=snapshot(config),
    )
    crud.flush(session)
    invalidar_client_cache()
    return config


_CLIENT_CACHE_TTL_S = 300.0
_CLIENT_CACHE_MAX_SIZE = 4


@dataclass
class _CachedClient:
    client: RsdClient
    touched_at: float


_client_cache: dict[str, _CachedClient] = {}
_client_cache_lock = threading.Lock()


def _client_cache_key(config: RsdConfig) -> str:
    # `config.senha` é o ciphertext gravado, não a senha em texto plano —
    # serve como parte da chave sem expor segredo em memória duplicada.
    return f"{config.base_url or _DEFAULT_BASE_URL}|{config.email}|{config.senha}"


def client_from_config(config: RsdConfig) -> RsdClient:
    """Devolve um `RsdClient` com sessão reaproveitada entre requests.

    Antes, cada rota criava um cliente novo e o `with` fechava a conexão ao
    fim do request, descartando cookies/CSRF — isso forçava um login
    completo a cada chamada (inclusive a cada 3s durante o poll do dossiê).
    Agora o cliente fica em cache por config, mantendo a sessão Django viva
    entre requests; `ensure_login`/o wrapper de request continuam cobrindo
    o caso de sessão expirada no portal.
    """
    if not configurado(config):
        raise RsdNotConfiguredError("Configure e-mail e senha do RSD em Configurações.")
    base_url = _validate_rsd_url(config.base_url or _DEFAULT_BASE_URL)
    key = _client_cache_key(config)
    agora = time.monotonic()
    expirados: list[RsdClient] = []
    with _client_cache_lock:
        for cache_key, entry in list(_client_cache.items()):
            if agora - entry.touched_at > _CLIENT_CACHE_TTL_S:
                entry.client._retire()  # noqa: SLF001
                expirados.append(entry.client)
                del _client_cache[cache_key]
        cached_entry: _CachedClient | None = _client_cache.get(key)
        if cached_entry is None:
            if len(_client_cache) >= _CLIENT_CACHE_MAX_SIZE:
                chave_antiga, antigo = min(
                    _client_cache.items(), key=lambda item: item[1].touched_at
                )
                antigo.client._retire()  # noqa: SLF001
                expirados.append(antigo.client)
                del _client_cache[chave_antiga]
            # Decripta antes de construir o cliente para falhar fechado, mas
            # não mantém a senha em nenhum atributo do objeto cacheado.
            senha_inicial = _decriptar_senha(config.senha)
            client = RsdClient(
                base_url=base_url,
                email=config.email.strip(),
                senha="",
            )
            del senha_inicial
            client._clear_password_after_login = True  # noqa: SLF001
            client._credential_provider = (  # noqa: SLF001
                lambda: _decriptar_senha(config.senha)
            )
            client.open()
            _client_cache[key] = _CachedClient(client=client, touched_at=agora)
        else:
            client = cached_entry.client
            cached_entry.touched_at = agora
    for old_client in expirados:
        old_client.close()
    return client


def client_from_values(
    *, email: str, senha: str, base_url: str, config: RsdConfig
) -> RsdClient:
    """`RsdClient` efêmero a partir de valores de formulário ainda não salvos.

    Usado por "Testar conexão": campo vazio cai para o valor já persistido
    em `config` (mesma semântica de `atualizar_config`). Não passa pelo
    cache de `client_from_config` — o chamador é responsável por abrir e
    fechar o client.
    """
    base_final = _validate_rsd_url(base_url or config.base_url or _DEFAULT_BASE_URL)
    email_final = (email or config.email).strip()
    senha_final = senha or _decriptar_senha(config.senha)
    if not email_final or not senha_final:
        raise RsdNotConfiguredError("Configure e-mail e senha do RSD em Configurações.")
    return RsdClient(
        base_url=base_final or _DEFAULT_BASE_URL, email=email_final, senha=senha_final
    )


def invalidar_client_cache() -> None:
    """Fecha e descarta clientes RSD em cache — chamado ao trocar config."""
    with _client_cache_lock:
        clientes = [entry.client for entry in _client_cache.values()]
        for client in clientes:
            client._retire()  # noqa: SLF001
        _client_cache.clear()
    for client in clientes:
        client.close()


_PAYLOAD_CREDENCIAL_KEYS = {"senha", "password", "email"}


def _sanitizar_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return {
        key: value
        for key, value in payload.items()
        if key.lower() not in _PAYLOAD_CREDENCIAL_KEYS
    }


def registrar_consulta(
    *,
    tipo: TipoConsultaRsd,
    placa: str,
    veiculo_id: int | None = None,
    usuario_id: int | None = None,
    payload: dict[str, Any] | None = None,
    campos_aplicados: dict[str, Any] | None = None,
    sucesso: bool,
    erro: str | None = None,
    dossie_id: int | None = None,
    status_dossie: str | None = None,
    duracao_ms: int | None = None,
) -> None:
    """Grava uma chamada ao portal RSD em sessão própria.

    As rotas de RSD chamam `detach_request_session` antes da chamada externa
    (ver docs/agents/transactions-rollbacks.md), então quando o resultado do
    portal chega a sessão do request já foi encerrada — não há sessão viva
    para gravar. Falha ao registrar é logada e não derruba a resposta ao
    usuário.
    """
    session = SessionLocal()
    try:
        session.add(
            RsdConsulta(
                tipo=tipo,
                placa=_normalizar_placa(placa),
                veiculo_id=veiculo_id,
                usuario_id=usuario_id,
                payload=_sanitizar_payload(payload),
                campos_aplicados=campos_aplicados,
                sucesso=sucesso,
                erro=erro,
                dossie_id=dossie_id,
                status_dossie=status_dossie,
                duracao_ms=duracao_ms,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("rsd_consulta_registro_falhou", tipo=tipo, placa=placa)
    finally:
        session.close()


def atualizar_consulta_dossie(
    *,
    dossie_id: int,
    payload: dict[str, Any] | None,
    status_dossie: str | None,
    sucesso: bool,
    erro: str | None = None,
) -> None:
    """Atualiza a linha de `rsd_consulta` já criada por `iniciar_unitaria`.

    Chamada quando o poll do lado do cliente encontra um status terminal — a
    consulta unitária em si continua sendo uma linha por dossiê, não uma por
    checagem de status.
    """
    session = SessionLocal()
    try:
        registro = (
            session.query(RsdConsulta)
            .filter_by(dossie_id=dossie_id)
            .order_by(RsdConsulta.id.desc())
            .first()
        )
        if registro is None:
            return
        registro.payload = _sanitizar_payload(payload)
        registro.status_dossie = status_dossie
        registro.sucesso = sucesso
        registro.erro = erro
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("rsd_consulta_atualizacao_falhou", dossie_id=dossie_id)
    finally:
        session.close()


def _filtros_consulta(
    stmt: Any,
    *,
    tipo: TipoConsultaRsd | None,
    placa: str | None,
    usuario_id: int | None,
    sucesso: bool | None,
    data_de: date | None,
    data_ate: date | None,
) -> Any:
    if tipo is not None:
        stmt = stmt.where(RsdConsulta.tipo == tipo)
    if placa:
        stmt = stmt.where(RsdConsulta.placa == placa)
    if usuario_id is not None:
        stmt = stmt.where(RsdConsulta.usuario_id == usuario_id)
    if sucesso is not None:
        stmt = stmt.where(RsdConsulta.sucesso == sucesso)
    if data_de is not None:
        stmt = stmt.where(
            RsdConsulta.criado_em >= datetime.combine(data_de, dtime.min, tzinfo=UTC)
        )
    if data_ate is not None:
        fim = datetime.combine(data_ate, dtime.min, tzinfo=UTC) + timedelta(days=1)
        stmt = stmt.where(RsdConsulta.criado_em < fim)
    return stmt


def listar_consultas(
    session: Session,
    *,
    tipo: TipoConsultaRsd | None = None,
    placa: str | None = None,
    usuario_id: int | None = None,
    sucesso: bool | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RsdConsulta]:
    """Lista consultas ordenadas da mais recente para a mais antiga."""
    placa_norm = _normalizar_placa(placa) if placa else None
    stmt = select(RsdConsulta).order_by(
        RsdConsulta.criado_em.desc(), RsdConsulta.id.desc()
    )
    stmt = _filtros_consulta(
        stmt,
        tipo=tipo,
        placa=placa_norm,
        usuario_id=usuario_id,
        sucesso=sucesso,
        data_de=data_de,
        data_ate=data_ate,
    )
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt))


def count_consultas(
    session: Session,
    *,
    tipo: TipoConsultaRsd | None = None,
    placa: str | None = None,
    usuario_id: int | None = None,
    sucesso: bool | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
) -> int:
    """Conta consultas com os mesmos filtros de `listar_consultas`."""
    placa_norm = _normalizar_placa(placa) if placa else None
    stmt = select(func.count()).select_from(RsdConsulta)
    stmt = _filtros_consulta(
        stmt,
        tipo=tipo,
        placa=placa_norm,
        usuario_id=usuario_id,
        sucesso=sucesso,
        data_de=data_de,
        data_ate=data_ate,
    )
    return int(session.scalar(stmt) or 0)


def get_consulta(session: Session, consulta_id: int) -> RsdConsulta | None:
    return session.get(RsdConsulta, consulta_id)


@dataclass
class RsdClient:
    """Cliente HTTP com sessão Django (cookies + CSRF)."""

    base_url: str
    email: str
    senha: str
    _client: httpx.Client | None = None
    _csrf: str | None = None
    _credential_provider: Callable[[], str] | None = field(
        default=None, repr=False, compare=False
    )
    _clear_password_after_login: bool = field(default=False, repr=False, compare=False)
    _retired: bool = field(default=False, repr=False, compare=False)
    _lock: threading.RLock = field(
        default_factory=threading.RLock, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self.base_url = _validate_rsd_url(self.base_url)

    def __enter__(self) -> RsdClient:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def open(self) -> None:
        with self._lock:
            if self._retired:
                raise RsdClientRetiredError("A sessão RSD foi invalidada.")
            if self._client is None:
                self._client = httpx.Client(
                    base_url=self.base_url,
                    timeout=_HTTP_TIMEOUT_S,
                    follow_redirects=False,
                    headers={"User-Agent": "xtreme-system-rsd/1.0"},
                )

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
            self._csrf = None
            self.senha = ""
            self._credential_provider = None

    def _retire(self) -> None:
        with self._lock:
            self._retired = True

    def _http(self) -> httpx.Client:
        with self._lock:
            if self._retired:
                raise RsdClientRetiredError("A sessão RSD foi invalidada.")
            if self._client is None:
                self.open()
        assert self._client is not None  # noqa: S101
        return self._client

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _extract_csrf(self, html: str) -> str:
        match = _CSRF_RE.search(html)
        if not match:
            raise RsdAuthError("CSRF token não encontrado na página de login.")
        return match.group(1)

    def _refresh_csrf_from_cookies(self) -> str | None:
        client = self._http()
        token = client.cookies.get("csrftoken")
        if token:
            self._csrf = token
        return self._csrf

    def _do_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._http().request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise RsdTimeoutError(
                "O portal RSD não respondeu a tempo. Tente novamente."
            ) from exc
        except httpx.HTTPError as exc:
            raise RsdConsultaError(
                "Falha ao comunicar com o portal RSD. Tente novamente."
            ) from exc

    def _sessao_expirou_no_corpo(self, resp: httpx.Response) -> bool:
        # Alguns endpoints (ex.: baixar_pdf) seguem redirect até um corpo
        # binário — não decodificar como texto para não estourar em
        # UnicodeDecodeError. Content-Type explícito não-textual, ou magic
        # bytes de PDF, descartam a checagem sem tocar em resp.text.
        ctype = resp.headers.get("Content-Type", "")
        if (ctype and "text" not in ctype) or resp.content.startswith(b"%PDF"):
            return False
        try:
            return "id_password" in resp.text
        except UnicodeDecodeError:
            return False

    def _sessao_expirou(self, resp: httpx.Response) -> bool:
        if resp.status_code in {401, 403}:
            return True
        if resp.status_code in {301, 302, 303, 307, 308}:
            return _LOGIN_PATH in (resp.headers.get("Location") or "")
        if resp.status_code != 200:
            return False
        return self._sessao_expirou_no_corpo(resp)

    def _request(
        self,
        method: str,
        path: str,
        *,
        follow_redirects: bool = False,
        retry_login: bool = True,
        headers_factory: Callable[[], dict[str, str]] | None = None,
        data_factory: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Ponto único de chamada HTTP: traduz erros de transporte para
        `RsdError` e reloga automaticamente em caso de sessão expirada.

        `headers_factory`, quando informado, é chamado de novo após o
        relogin — os headers passados em `kwargs` podem carregar um CSRF
        token que fica obsoleto assim que a sessão é renovada.
        """
        with self._lock:
            url = _validate_rsd_url(self._url(path), redirect=True)

            def _request_kwargs() -> dict[str, Any]:
                request_kwargs = dict(kwargs)
                if data_factory is not None:
                    request_kwargs["data"] = data_factory()
                if headers_factory is not None:
                    request_kwargs["headers"] = headers_factory()
                return request_kwargs

            def _request_with_validated_redirects() -> httpx.Response:
                current_method = method
                current_url = url
                for _ in range(5):
                    resp = self._do_request(
                        current_method,
                        current_url,
                        follow_redirects=False,
                        **_request_kwargs(),
                    )
                    destination = _validated_redirect(current_url, resp)
                    if destination is None:
                        return resp
                    if not follow_redirects:
                        return resp
                    response_status = resp.status_code
                    resp.close()
                    current_url = destination
                    if response_status in {301, 302, 303}:
                        current_method = "GET"
                raise RsdConsultaError(
                    "O portal RSD excedeu o limite de redirecionamentos."
                )

            resp = _request_with_validated_redirects()
            if retry_login and self._sessao_expirou(resp):
                logger.warning("rsd_sessao_expirada", method=method, path=path)
                self.login()
                resp = _request_with_validated_redirects()
            return resp

    def login(self) -> None:
        with self._lock:
            client = self._http()
            password = self.senha
            if not password and self._credential_provider is not None:
                password = self._credential_provider()
            if not password:
                raise RsdEncryptionError(
                    "A senha RSD não está disponível para renovar a sessão."
                )
            login_url = self._url(_LOGIN_PATH)
            try:
                try:
                    get_resp = client.get(login_url, params={"next": _UNITARIA_PATH})
                    _validated_redirect(login_url, get_resp)
                    get_resp.raise_for_status()
                except httpx.TimeoutException as exc:
                    raise RsdTimeoutError(
                        "O portal RSD não respondeu a tempo ao abrir a página de login."
                    ) from exc
                except httpx.HTTPError as exc:
                    raise RsdAuthError(
                        "Falha ao acessar a página de login do portal RSD."
                    ) from exc
                csrf = self._extract_csrf(get_resp.text)
                self._csrf = csrf
                try:
                    post_resp = client.post(
                        login_url,
                        data={
                            "csrfmiddlewaretoken": csrf,
                            "login": self.email,
                            "password": password,
                            "next": _UNITARIA_PATH,
                        },
                        headers={
                            "Origin": self.base_url,
                            "Referer": f"{login_url}?next={_UNITARIA_PATH}",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                except httpx.TimeoutException as exc:
                    raise RsdTimeoutError(
                        "O portal RSD não respondeu a tempo ao efetuar login."
                    ) from exc
                except httpx.HTTPError as exc:
                    raise RsdAuthError("Falha ao enviar login ao portal RSD.") from exc
                _validated_redirect(login_url, post_resp)
                if post_resp.status_code == 403:
                    raise RsdAuthError("Login rejeitado (CSRF/Origin).")
                # Sucesso: 302 para /dossie/unitaria/; falha: 200 com formulário
                if post_resp.status_code == 200 and "id_password" in post_resp.text:
                    raise RsdAuthError("E-mail ou senha inválidos no portal RSD.")
                if post_resp.status_code not in (200, 302, 303):
                    raise RsdAuthError(
                        f"Falha no login RSD (HTTP {post_resp.status_code})."
                    )
                if not client.cookies.get("sessionid"):
                    raise RsdAuthError("Sessão RSD não foi criada após o login.")
                self._refresh_csrf_from_cookies()
                logger.info("rsd_login_ok", email=self.email)
            finally:
                if self._clear_password_after_login:
                    self.senha = ""

    def ensure_login(self) -> None:
        if self._http().cookies.get("sessionid") and self._csrf:
            return
        self.login()

    def _csrf_headers(self, referer_path: str) -> dict[str, str]:
        self.ensure_login()
        csrf = self._csrf or self._refresh_csrf_from_cookies()
        if not csrf:
            raise RsdAuthError("CSRF token ausente após login.")
        return {
            "X-CSRFToken": csrf,
            "Origin": self.base_url,
            "Referer": self._url(referer_path),
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _refresh_unitaria_csrf(self) -> str:
        page = self._request("GET", _UNITARIA_PATH, follow_redirects=True)
        csrf = self._extract_csrf(page.text)
        self._csrf = csrf
        return csrf

    def _check_capability(
        self, *, label: str, path: str, markers: tuple[str, ...]
    ) -> None:
        response = self._request("GET", path, follow_redirects=True)
        # Portal fora do ar não é falta de permissão: sem esta distinção, uma
        # indisponibilidade rebaixa a credencial (ver _marcar_falha_credencial).
        upstream = _erro_upstream_do_portal(response)
        if upstream is not None:
            raise RsdIndisponivelError(
                _MSG_PORTAL_INDISPONIVEL,
                status_portal=response.status_code,
                detalhe_portal=upstream,
            )
        if response.status_code >= 400 or not all(
            marker in response.text for marker in markers
        ):
            raise RsdCapabilityError(
                f"A conta RSD não tem permissão ou acesso para {label}.",
                status_portal=response.status_code,
            )

    def testar_conexao(self) -> None:
        self.login()
        self._check_capability(
            label="puxar dados",
            path=_ATPV_NOVA_PATH,
            markers=('name="placa"',),
        )
        self._check_capability(
            label="consulta unitária",
            path=_UNITARIA_PATH,
            markers=('class="dossie-form"', 'name="placa"'),
        )

    def _puxar_dados_resposta(self, placa_norm: str) -> httpx.Response:
        """POST de puxar dados, repetido quando o motor do portal falha.

        A consulta não altera estado no portal, então repetir é seguro — e o
        502 do motor costuma ser um blip que a tentativa seguinte já resolve.
        """
        detalhe = ""
        resp: httpx.Response | None = None
        for tentativa in range(len(_RETRY_BACKOFF_S) + 1):
            resp = self._request(
                "POST",
                _PUXAR_DADOS_PATH,
                data={"placa": placa_norm},
                headers_factory=lambda: self._csrf_headers(_ATPV_NOVA_PATH),
            )
            upstream = _erro_upstream_do_portal(resp)
            if upstream is None:
                return resp
            detalhe = upstream
            logger.warning(
                "rsd_puxar_dados_upstream_indisponivel",
                tentativa=tentativa + 1,
                status=resp.status_code,
                detalhe_portal=detalhe,
            )
            if tentativa < len(_RETRY_BACKOFF_S):
                time.sleep(_RETRY_BACKOFF_S[tentativa])
        assert resp is not None  # noqa: S101
        raise RsdIndisponivelError(
            _MSG_PORTAL_INDISPONIVEL,
            status_portal=resp.status_code,
            detalhe_portal=detalhe,
        )

    def puxar_dados(self, placa: str) -> PuxarDadosResult:
        placa_norm = _normalizar_placa(placa)
        if not placa_norm:
            raise RsdConsultaError("Informe a placa para puxar dados.")
        resp = self._puxar_dados_resposta(placa_norm)
        if resp.status_code >= 400:
            raise RsdConsultaError(
                _msg_http(resp, "Falha ao puxar dados no RSD."),
                status_portal=resp.status_code,
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise RsdConsultaError("Resposta inválida do RSD (não-JSON).") from exc
        if isinstance(payload, dict) and payload.get("erro"):
            raise RsdConsultaError(str(payload["erro"]))
        try:
            result = PuxarDadosResult.model_validate(payload)
        except ValidationError as exc:
            raise RsdConsultaError("Resposta inválida do RSD.") from exc
        if result.outro_estado:
            raise RsdConsultaError(
                "Placa de outro estado — "
                "use a consulta Base de Outros Estados no portal RSD."
            )
        return result

    def iniciar_unitaria(self, placa: str) -> int:
        """Abre um dossiê no portal e devolve o `dossie_id`, sem aguardar conclusão."""
        placa_norm = _normalizar_placa(placa)
        if not placa_norm:
            raise RsdConsultaError("Informe a placa ou chassi para consultar.")
        self.ensure_login()
        resp = self._request(
            "POST",
            _UNITARIA_PATH,
            data_factory=lambda: {
                "csrfmiddlewaretoken": self._refresh_unitaria_csrf(),
                "fonte": "be",
                "placa": placa_norm,
            },
            headers_factory=lambda: self._csrf_headers(_UNITARIA_PATH),
        )
        if resp.status_code not in (302, 303):
            # Sem retry aqui: o POST cria um dossiê no portal, repetir
            # duplicaria a consulta (e a cobrança) quando ela já tiver saído.
            upstream = _erro_upstream_do_portal(resp)
            if upstream is not None:
                raise RsdIndisponivelError(
                    _MSG_PORTAL_INDISPONIVEL,
                    status_portal=resp.status_code,
                    detalhe_portal=upstream,
                )
            raise RsdConsultaError(
                _msg_http(resp, "Falha ao iniciar consulta unitária."),
                status_portal=resp.status_code,
            )
        location = resp.headers.get("Location") or ""
        match = _DOSSIE_ID_RE.search(location)
        if not match:
            # Não repassa o Location cru ao usuário — é detalhe interno do
            # portal; fica só no log técnico.
            logger.warning(
                "rsd_iniciar_unitaria_redirect_inesperado", location=location
            )
            raise RsdConsultaError(
                "Falha ao iniciar consulta unitária: redirect inesperado do portal."
            )
        return int(match.group(1))

    def consultar_unitaria_be(
        self, placa: str, *, poll_timeout_s: float = _POLL_TIMEOUT_S
    ) -> UnitariaResult:
        """Inicia e aguarda a consulta até um status terminal (uso síncrono/CLI)."""
        dossie_id = self.iniciar_unitaria(placa)
        status_payload = self._poll_status(dossie_id, timeout_s=poll_timeout_s)
        return UnitariaResult(
            dossie_id=dossie_id,
            status=str(status_payload.get("status") or ""),
            status_display=status_payload.get("status_display"),
            error=status_payload.get("error"),
            portais=list(status_payload.get("portais") or []),
            has_consolidado=bool(status_payload.get("has_consolidado")),
            is_terminal=True,
        )

    def status_unitaria(self, dossie_id: int) -> UnitariaResult:
        """Uma única checagem de status, para poll do lado do cliente via htmx."""
        self.ensure_login()
        payload = self._fetch_status_once(dossie_id)
        terminal = bool(payload.get("is_terminal")) or payload.get("status") in {
            "done",
            "error",
            "aborted_by_user",
        }
        return UnitariaResult(
            dossie_id=dossie_id,
            status=str(payload.get("status") or ""),
            status_display=payload.get("status_display"),
            error=payload.get("error"),
            portais=list(payload.get("portais") or []),
            has_consolidado=bool(payload.get("has_consolidado")),
            is_terminal=terminal,
        )

    def _fetch_status_once(self, dossie_id: int) -> dict[str, Any]:
        resp = self._request(
            "GET",
            f"/dossie/{dossie_id}/status/",
            headers={"Accept": "application/json"},
        )
        if resp.status_code >= 400:
            upstream = _erro_upstream_do_portal(resp)
            if upstream is not None:
                raise RsdIndisponivelError(
                    _MSG_PORTAL_INDISPONIVEL,
                    status_portal=resp.status_code,
                    detalhe_portal=upstream,
                )
            raise RsdConsultaError(
                _msg_http(resp, f"Falha ao consultar status do dossiê {dossie_id}."),
                status_portal=resp.status_code,
            )
        try:
            payload: dict[str, Any] = resp.json()
        except ValueError as exc:
            raise RsdConsultaError("Status do dossiê não é JSON.") from exc
        if payload.get("status") == "error" and payload.get("error"):
            raise RsdConsultaError(str(payload["error"]))
        if payload.get("needs_captcha"):
            raise RsdConsultaError(
                "Consulta exige captcha no portal RSD — conclua manualmente."
            )
        return payload

    def _poll_status(self, dossie_id: int, *, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        last: dict[str, Any] = {}
        erros_consecutivos = 0
        while time.monotonic() < deadline:
            try:
                last = self._fetch_status_once(dossie_id)
            except RsdError as exc:
                erros_consecutivos += 1
                logger.warning(
                    "rsd_poll_falha_transitoria",
                    dossie_id=dossie_id,
                    tentativa=erros_consecutivos,
                    erro=str(exc),
                )
                if erros_consecutivos >= _POLL_MAX_ERROS_CONSECUTIVOS:
                    raise
                time.sleep(_POLL_INTERVAL_S)
                continue
            erros_consecutivos = 0
            if last.get("is_terminal") or last.get("status") in {
                "done",
                "error",
                "aborted_by_user",
            }:
                return last
            time.sleep(_POLL_INTERVAL_S)
        raise RsdTimeoutError(
            f"Consulta do dossiê {dossie_id} excedeu {int(timeout_s)}s."
        )

    def baixar_pdf(self, dossie_id: int) -> bytes:
        self.ensure_login()
        resp = self._request("GET", f"/dossie/{dossie_id}/pdf/", follow_redirects=True)
        if resp.status_code >= 400:
            upstream = _erro_upstream_do_portal(resp)
            if upstream is not None:
                raise RsdIndisponivelError(
                    _MSG_PORTAL_INDISPONIVEL,
                    status_portal=resp.status_code,
                    detalhe_portal=upstream,
                )
            raise RsdConsultaError(
                _msg_http(resp, f"Falha ao baixar PDF do dossiê {dossie_id}."),
                status_portal=resp.status_code,
            )
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "pdf" not in ctype and not resp.content.startswith(b"%PDF"):
            raise RsdConsultaError("Resposta do portal não é um PDF.")
        return resp.content


_ESPECIES_MOTO = ("motocicleta", "motoneta", "ciclomotor", "triciclo", "quadriciclo")

# Campos de texto que vêm do portal 1:1 para uma coluna de `Veiculo`.
_CAMPOS_TEXTO_DIRETOS = (
    "chassi",
    "renavam",
    "cor",
    "tipo_documento",
    "categoria",
    "especie",
    "combustivel",
    "potencia",
    "cilindrada",
    "numero_motor",
    "procedencia",
    "municipio",
    "proprietario_anterior",
)


# Prefixos que o DENATRAN usa no lugar da marca para veículo importado:
# em "I/VW JETTA" o "I" não é fabricante, é procedência.
_PREFIXOS_IMPORTADO = frozenset({"I", "IMP", "IMPORT", "IMPORTADO"})

_PROCEDENCIA_IMPORTADO = "Importado"

# Grafia do CRLV → nome canônico da marca. Serve a dois usos: expandir as
# abreviações do documento ("CHEV" é o mesmo fabricante que alguém digita
# como "CHEVROLET", e `marca` é coluna de busca) e, no ramo importado, saber
# onde a marca termina e o modelo começa — daí as entradas de nome completo
# e as de duas palavras, que um corte no primeiro espaço quebraria.
_MARCAS_CANONICAS = {
    "ALFA ROMEO": "ALFA ROMEO",
    "AUDI": "AUDI",
    "BMW": "BMW",
    "BYD": "BYD",
    "CAOA CHERY": "CAOA CHERY",
    "CHERY": "CHERY",
    "CHEV": "CHEVROLET",
    "CHEVROLET": "CHEVROLET",
    "CHRYSLER": "CHRYSLER",
    "CITROEN": "CITROEN",
    "DODGE": "DODGE",
    "FIAT": "FIAT",
    "FORD": "FORD",
    "GM": "CHEVROLET",
    "GWM": "GWM",
    "HONDA": "HONDA",
    "HYUNDAI": "HYUNDAI",
    "IVECO": "IVECO",
    "JAC": "JAC",
    "JAGUAR": "JAGUAR",
    "JEEP": "JEEP",
    "KIA": "KIA",
    "LAND ROVER": "LAND ROVER",
    "LEXUS": "LEXUS",
    "M.BENZ": "MERCEDES-BENZ",
    "MBENZ": "MERCEDES-BENZ",
    "MERCEDES BENZ": "MERCEDES-BENZ",
    "MERCEDES-BENZ": "MERCEDES-BENZ",
    "MINI": "MINI",
    "MITSUBISHI": "MITSUBISHI",
    "MMC": "MITSUBISHI",
    "NISSAN": "NISSAN",
    "PEUGEOT": "PEUGEOT",
    "PORSCHE": "PORSCHE",
    "RAM": "RAM",
    "RANGE ROVER": "LAND ROVER",
    "RENAULT": "RENAULT",
    "SSANGYONG": "SSANGYONG",
    "SUBARU": "SUBARU",
    "TOYOTA": "TOYOTA",
    "TROLLER": "TROLLER",
    "VOLVO": "VOLVO",
    "VW": "VOLKSWAGEN",
    "VOLKSWAGEN": "VOLKSWAGEN",
    # Motos
    "APRILIA": "APRILIA",
    "BENELLI": "BENELLI",
    "CAN AM": "CAN-AM",
    "DAFRA": "DAFRA",
    "DUCATI": "DUCATI",
    "HAOJUE": "HAOJUE",
    "HARLEY DAVIDSON": "HARLEY-DAVIDSON",
    "HUSQVARNA": "HUSQVARNA",
    "KASINSKI": "KASINSKI",
    "KAWASAKI": "KAWASAKI",
    "KTM": "KTM",
    "MV AGUSTA": "MV AGUSTA",
    "ROYAL ENFIELD": "ROYAL ENFIELD",
    "SHINERAY": "SHINERAY",
    "SUNDOWN": "SUNDOWN",
    "SUZUKI": "SUZUKI",
    "TRAXX": "TRAXX",
    "TRIUMPH": "TRIUMPH",
    "YAMAHA": "YAMAHA",
}

# Maior número de palavras entre as chaves acima — limite da busca por prefixo.
_MAX_PALAVRAS_MARCA = max(len(chave.split()) for chave in _MARCAS_CANONICAS)


def _chave_marca(texto: str) -> str:
    return " ".join(texto.upper().split())


def _partir_marca_conhecida(texto: str) -> tuple[str | None, str]:
    """Separa "VW JETTA" em marca e modelo consultando `_MARCAS_CANONICAS`.

    Sem o "/" do CRLV não há sintaxe que diga onde a marca termina, só
    conhecimento: "VW JETTA" tem marca de uma palavra e "ROYAL ENFIELD
    HIMALAYA" de duas. Testa do prefixo mais longo para o mais curto para
    que a marca composta ganhe da simples. Marca desconhecida devolve
    `None` — quem chama omite o campo em vez de gravar um palpite.
    """
    palavras = texto.split()
    for tamanho in range(min(_MAX_PALAVRAS_MARCA, len(palavras)), 0, -1):
        marca = _MARCAS_CANONICAS.get(_chave_marca(" ".join(palavras[:tamanho])))
        if marca:
            return marca, " ".join(palavras[tamanho:])
    return None, texto


def _marca_modelo(texto: str) -> tuple[str | None, str | None, bool]:
    """Quebra o `marca_modelo` do CRLV em `(marca, modelo, importado)`.

    O formato é "MARCA/MODELO", mas o importado vem como "I/VW JETTA": o
    slot da marca carrega a procedência e o fabricante real fica junto do
    modelo. `marca` ou `modelo` em `None` significa "não sei" — quem chama
    omite a chave e preserva o que já estava gravado no veículo.
    """
    marca_bruta, separador, resto = texto.partition("/")
    marca_bruta, resto = marca_bruta.strip(), resto.strip()
    if not separador:
        # Sem "/" não dá para saber onde a marca acaba; o texto inteiro é o
        # melhor palpite de modelo e a marca fica como está no veículo.
        return None, texto.strip() or None, False
    if not resto:
        # "MARCA/" sem modelo: só o slot da marca é aproveitável, e mesmo
        # ele não serve se for o prefixo de importado.
        if _chave_marca(marca_bruta) in _PREFIXOS_IMPORTADO:
            return None, None, True
        return None, marca_bruta or None, False
    if _chave_marca(marca_bruta) in _PREFIXOS_IMPORTADO:
        marca, modelo = _partir_marca_conhecida(resto)
        return marca, modelo or None, True
    if not marca_bruta:
        return None, resto, False
    return _MARCAS_CANONICAS.get(_chave_marca(marca_bruta), marca_bruta), resto, False


def _tipo_do_veiculo(dados: PuxarDadosResult) -> str | None:
    """Deriva carro/moto da espécie/categoria do CRLV.

    O portal não devolve o `tipo` no vocabulário do sistema (só temos
    `carro` e `moto`), mas a espécie do documento distingue as duas famílias.
    Sem sinal reconhecível devolve `None` — melhor deixar o campo como está
    do que classificar errado um veículo já cadastrado.
    """
    texto = f"{dados.especie or ''} {dados.categoria or ''}".strip().lower()
    if not texto:
        return None
    if any(termo in texto for termo in _ESPECIES_MOTO):
        return "moto"
    if "automovel" in texto or "automóvel" in texto or "caminhonete" in texto:
        return "carro"
    return None


def mapear_para_veiculo(dados: PuxarDadosResult, *, prefix: str = "") -> dict[str, Any]:
    """Campos do formulário de veículo a partir do JSON puxar-dados.

    Só entram no resultado os campos que o portal realmente devolveu: uma
    chave ausente preserva o valor já gravado, em vez de apagá-lo.
    """
    out: dict[str, Any] = {}
    importado = False
    if dados.marca_modelo:
        marca, modelo, importado = _marca_modelo(dados.marca_modelo)
        if modelo:
            out[f"{prefix}modelo"] = modelo
        if marca:
            out[f"{prefix}marca"] = marca
    if dados.ano is not None:
        out[f"{prefix}ano"] = dados.ano
    for campo in _CAMPOS_TEXTO_DIRETOS:
        valor = getattr(dados, campo, None)
        if valor:
            out[f"{prefix}{campo}"] = str(valor).strip()
    # O prefixo "I/" é a única procedência que `puxar-dados` entrega hoje —
    # o campo `procedencia` do JSON vem sempre vazio. Só preenche se o portal
    # não tiver dito nada: se um dia ele mandar o campo, ele é a fonte melhor.
    if importado and not out.get(f"{prefix}procedencia"):
        out[f"{prefix}procedencia"] = _PROCEDENCIA_IMPORTADO
    if dados.nome_proprietario:
        out[f"{prefix}proprietario_atual"] = dados.nome_proprietario
    if dados.cpf_cnpj:
        out[f"{prefix}proprietario_documento"] = dados.cpf_cnpj
    if dados.placa:
        out[f"{prefix}placa"] = dados.placa
    tipo = _tipo_do_veiculo(dados)
    if tipo:
        out[f"{prefix}tipo"] = tipo
    return out


def _normalizar_placa(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def _erro_upstream_do_portal(resp: httpx.Response) -> str | None:
    """Texto cru do portal quando a falha veio do backend dele, senão `None`.

    Cobre dois formatos: 5xx do próprio portal e o embrulho que ele usa para
    o motor (status 4xx com `{"erro": "...: motor respondeu 502"}`).
    """
    if resp.status_code in _STATUS_UPSTREAM:
        return _msg_http(resp, f"O portal RSD falhou (HTTP {resp.status_code}).")
    try:
        data = resp.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    msg = str(data.get("erro") or data.get("error") or "")
    return msg if _MOTOR_5XX_RE.search(msg) else None


def _msg_http(resp: httpx.Response, fallback: str) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("erro"):
            msg = str(data["erro"])
            if len(msg) > _MSG_PORTAL_MAX_LEN:
                logger.warning(
                    "rsd_mensagem_portal_truncada", tamanho_original=len(msg)
                )
                msg = msg[:_MSG_PORTAL_MAX_LEN].rstrip() + "…"
            return msg
    except ValueError:
        pass
    return f"{fallback} (HTTP {resp.status_code})."
