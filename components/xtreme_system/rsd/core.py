"""Integração com o portal RSD (lojas.rsdsistema.com.br).

Autentica por sessão Django (cookie + CSRF). Não há API REST pública:
consulta unitária cria um dossiê e faz poll em /dossie/<id>/status/;
puxar dados usa POST /atpv/puxar-dados/ (JSON).
"""

from __future__ import annotations

import base64
import hashlib
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from enum import StrEnum
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import JSON, DateTime, ForeignKey, Index, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base, SessionLocal

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rsd_encryption_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def _get_fernet() -> Fernet:
    # Chave arbitrária -> chave Fernet válida (32 bytes url-safe base64), para
    # não exigir que RSD_ENCRYPTION_KEY já venha nesse formato específico.
    digest = hashlib.sha256(get_settings().rsd_encryption_key.encode("utf-8")).digest()
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
    except InvalidToken:
        # Valor gravado em texto plano antes desta feature — mantém
        # funcionando até a próxima atualização de config recodificar.
        return valor


_CONFIG_ID = 1
_DEFAULT_BASE_URL = "https://lojas.rsdsistema.com.br"
_LOGIN_PATH = "/accounts/login/"
_UNITARIA_PATH = "/dossie/unitaria/"
_PUXAR_DADOS_PATH = "/atpv/puxar-dados/"
_CSRF_RE = re.compile(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"')
_DOSSIE_ID_RE = re.compile(r"/dossie/(\d+)/?")
_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 120.0
_HTTP_TIMEOUT_S = 30.0
_SESSION_EXPIRED_STATUS_CODES = frozenset({301, 302, 303, 307, 308, 401, 403})


class RsdError(Exception):
    """Erro genérico da integração RSD."""


class RsdNotConfiguredError(RsdError):
    """Credenciais RSD ainda não configuradas."""


class RsdAuthError(RsdError):
    """Falha de login (credenciais ou CSRF)."""


class RsdTimeoutError(RsdError):
    """Uma chamada ao portal RSD excedeu o tempo de espera."""


class RsdConsultaError(RsdError):
    """Portal retornou erro na consulta."""


class RsdConfig(Base):
    __tablename__ = "rsd_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(default="", server_default="")
    senha: Mapped[str] = mapped_column(default="", server_default="")
    base_url: Mapped[str] = mapped_column(
        default=_DEFAULT_BASE_URL, server_default=_DEFAULT_BASE_URL
    )


class RsdConfigUpdate(BaseModel):
    email: str = ""
    senha: str = ""
    base_url: str = _DEFAULT_BASE_URL


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


class PuxarDadosResult(BaseModel):
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
    return bool(config.email.strip() and config.senha)


def atualizar_config(
    session: Session, data: RsdConfigUpdate, actor_id: int | None = None
) -> RsdConfig:
    config = get_config(session)
    antes = snapshot(config)
    config.email = data.email.strip()
    if data.senha:
        config.senha = _encriptar_senha(data.senha)
    base = (data.base_url or _DEFAULT_BASE_URL).strip().rstrip("/")
    config.base_url = base or _DEFAULT_BASE_URL
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
    return config


def client_from_config(config: RsdConfig) -> RsdClient:
    if not configurado(config):
        raise RsdNotConfiguredError("Configure e-mail e senha do RSD em Configurações.")
    return RsdClient(
        base_url=config.base_url or _DEFAULT_BASE_URL,
        email=config.email,
        senha=_decriptar_senha(config.senha),
    )


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

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def __enter__(self) -> RsdClient:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def open(self) -> None:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=_HTTP_TIMEOUT_S,
                follow_redirects=False,
                headers={"User-Agent": "xtreme-system-rsd/1.0"},
            )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._csrf = None

    def _http(self) -> httpx.Client:
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

    def login(self) -> None:
        client = self._http()
        login_url = self._url(_LOGIN_PATH)
        get_resp = client.get(login_url, params={"next": _UNITARIA_PATH})
        get_resp.raise_for_status()
        csrf = self._extract_csrf(get_resp.text)
        self._csrf = csrf
        post_resp = client.post(
            login_url,
            data={
                "csrfmiddlewaretoken": csrf,
                "login": self.email,
                "password": self.senha,
                "next": _UNITARIA_PATH,
            },
            headers={
                "Origin": self.base_url,
                "Referer": f"{login_url}?next={_UNITARIA_PATH}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if post_resp.status_code == 403:
            raise RsdAuthError("Login rejeitado (CSRF/Origin).")
        # Sucesso: 302 para /dossie/unitaria/; falha: 200 com formulário
        if post_resp.status_code == 200 and "id_password" in post_resp.text:
            raise RsdAuthError("E-mail ou senha inválidos no portal RSD.")
        if post_resp.status_code not in (200, 302, 303):
            raise RsdAuthError(f"Falha no login RSD (HTTP {post_resp.status_code}).")
        if not client.cookies.get("sessionid"):
            raise RsdAuthError("Sessão RSD não foi criada após o login.")
        self._refresh_csrf_from_cookies()
        logger.info("rsd_login_ok")

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

    def testar_conexao(self) -> None:
        self.login()

    def _post_puxar_dados(self, placa: str, headers: dict[str, str]) -> httpx.Response:
        try:
            return self._http().post(
                self._url(_PUXAR_DADOS_PATH),
                data={"placa": placa},
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise RsdTimeoutError(
                "O portal RSD não respondeu a tempo ao puxar os dados. Tente novamente."
            ) from exc

    def puxar_dados(self, placa: str) -> PuxarDadosResult:
        placa_norm = _normalizar_placa(placa)
        if not placa_norm:
            raise RsdConsultaError("Informe a placa para puxar dados.")
        headers = self._csrf_headers("/atpv/nova/")
        resp = self._post_puxar_dados(placa_norm, headers)
        if resp.status_code in _SESSION_EXPIRED_STATUS_CODES:
            # Sessão expirou — reloga uma vez
            self.login()
            headers = self._csrf_headers("/atpv/nova/")
            resp = self._post_puxar_dados(placa_norm, headers)
        if resp.status_code >= 400:
            raise RsdConsultaError(_msg_http(resp, "Falha ao puxar dados no RSD."))
        try:
            payload = resp.json()
        except ValueError as exc:
            raise RsdConsultaError("Resposta inválida do RSD (não-JSON).") from exc
        if isinstance(payload, dict) and payload.get("erro"):
            raise RsdConsultaError(str(payload["erro"]))
        result = PuxarDadosResult.model_validate(payload)
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
        # CSRF fresco da própria página unitária
        page = self._http().get(self._url(_UNITARIA_PATH), follow_redirects=True)
        if page.status_code == 200 and "id_password" in page.text:
            self.login()
            page = self._http().get(self._url(_UNITARIA_PATH), follow_redirects=True)
        page.raise_for_status()
        csrf = self._extract_csrf(page.text)
        self._csrf = csrf
        resp = self._http().post(
            self._url(_UNITARIA_PATH),
            data={
                "csrfmiddlewaretoken": csrf,
                "fonte": "be",
                "placa": placa_norm,
            },
            headers={
                "Origin": self.base_url,
                "Referer": self._url(_UNITARIA_PATH),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            follow_redirects=False,
        )
        if resp.status_code not in (302, 303):
            raise RsdConsultaError(
                _msg_http(resp, "Falha ao iniciar consulta unitária.")
            )
        location = resp.headers.get("Location") or ""
        match = _DOSSIE_ID_RE.search(location)
        if not match:
            raise RsdConsultaError(
                f"Redirect inesperado da consulta unitária: {location or '(vazio)'}"
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
        status_url = self._url(f"/dossie/{dossie_id}/status/")
        resp = self._http().get(status_url, headers={"Accept": "application/json"})
        if resp.status_code >= 400:
            raise RsdConsultaError(
                _msg_http(resp, f"Falha ao consultar status do dossiê {dossie_id}.")
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
        while time.monotonic() < deadline:
            last = self._fetch_status_once(dossie_id)
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
        resp = self._http().get(
            self._url(f"/dossie/{dossie_id}/pdf/"),
            follow_redirects=True,
        )
        if resp.status_code >= 400:
            raise RsdConsultaError(
                _msg_http(resp, f"Falha ao baixar PDF do dossiê {dossie_id}.")
            )
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "pdf" not in ctype and not resp.content.startswith(b"%PDF"):
            raise RsdConsultaError("Resposta do portal não é um PDF.")
        return resp.content


def mapear_para_veiculo(dados: PuxarDadosResult, *, prefix: str = "") -> dict[str, Any]:
    """Campos do formulário de veículo a partir do JSON puxar-dados."""
    out: dict[str, Any] = {}
    if dados.marca_modelo:
        marca, separador, resto = dados.marca_modelo.partition("/")
        out[f"{prefix}modelo"] = (
            resto.strip() if separador and resto.strip() else dados.marca_modelo
        )
        if separador and marca.strip():
            out[f"{prefix}marca"] = marca.strip()
    if dados.ano is not None:
        out[f"{prefix}ano"] = dados.ano
    if dados.cor:
        out[f"{prefix}cor"] = dados.cor
    if dados.chassi:
        out[f"{prefix}chassi"] = dados.chassi
    if dados.renavam:
        out[f"{prefix}renavam"] = dados.renavam
    if dados.nome_proprietario:
        out[f"{prefix}proprietario_registrado"] = dados.nome_proprietario
    if dados.cpf_cnpj:
        out[f"{prefix}proprietario_documento"] = dados.cpf_cnpj
    if dados.uf:
        out[f"{prefix}proprietario_uf"] = dados.uf
    if dados.placa:
        out[f"{prefix}placa"] = dados.placa
    return out


def _normalizar_placa(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def _msg_http(resp: httpx.Response, fallback: str) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("erro"):
            return str(data["erro"])
    except ValueError:
        pass
    return f"{fallback} (HTTP {resp.status_code})."
