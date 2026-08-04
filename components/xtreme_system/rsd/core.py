"""Integração com o portal RSD (lojas.rsdsistema.com.br).

Autentica por sessão Django (cookie + CSRF). Não há API REST pública:
consulta unitária cria um dossiê e faz poll em /dossie/<id>/status/;
puxar dados usa POST /atpv/puxar-dados/ (JSON).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx
import structlog
from pydantic import BaseModel, Field
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

logger = structlog.get_logger(__name__)

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


class RsdError(Exception):
    """Erro genérico da integração RSD."""


class RsdNotConfiguredError(RsdError):
    """Credenciais RSD ainda não configuradas."""


class RsdAuthError(RsdError):
    """Falha de login (credenciais ou CSRF)."""


class RsdTimeoutError(RsdError):
    """Consulta unitária excedeu o tempo de espera."""


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
        config.senha = data.senha
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
        senha=config.senha,
    )


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

    def puxar_dados(self, placa: str) -> PuxarDadosResult:
        placa_norm = _normalizar_placa(placa)
        if not placa_norm:
            raise RsdConsultaError("Informe a placa para puxar dados.")
        headers = self._csrf_headers("/atpv/nova/")
        resp = self._http().post(
            self._url(_PUXAR_DADOS_PATH),
            data={"placa": placa_norm},
            headers=headers,
        )
        if resp.status_code in (401, 403):
            # Sessão expirou — reloga uma vez
            self.login()
            headers = self._csrf_headers("/atpv/nova/")
            resp = self._http().post(
                self._url(_PUXAR_DADOS_PATH),
                data={"placa": placa_norm},
                headers=headers,
            )
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

    def consultar_unitaria_be(
        self, placa: str, *, poll_timeout_s: float = _POLL_TIMEOUT_S
    ) -> UnitariaResult:
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
        dossie_id = int(match.group(1))
        status_payload = self._poll_status(dossie_id, timeout_s=poll_timeout_s)
        return UnitariaResult(
            dossie_id=dossie_id,
            status=str(status_payload.get("status") or ""),
            status_display=status_payload.get("status_display"),
            error=status_payload.get("error"),
            portais=list(status_payload.get("portais") or []),
            has_consolidado=bool(status_payload.get("has_consolidado")),
        )

    def _poll_status(self, dossie_id: int, *, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        status_url = self._url(f"/dossie/{dossie_id}/status/")
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            resp = self._http().get(status_url, headers={"Accept": "application/json"})
            if resp.status_code >= 400:
                raise RsdConsultaError(
                    _msg_http(resp, f"Falha ao consultar status do dossiê {dossie_id}.")
                )
            try:
                last = resp.json()
            except ValueError as exc:
                raise RsdConsultaError("Status do dossiê não é JSON.") from exc
            if last.get("is_terminal") or last.get("status") in {
                "done",
                "error",
                "aborted_by_user",
            }:
                if last.get("status") == "error" and last.get("error"):
                    raise RsdConsultaError(str(last["error"]))
                return last
            if last.get("needs_captcha"):
                raise RsdConsultaError(
                    "Consulta exige captcha no portal RSD — conclua manualmente."
                )
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


def mapear_para_veiculo(dados: PuxarDadosResult) -> dict[str, Any]:
    """Campos do formulário de veículo a partir do JSON puxar-dados."""
    out: dict[str, Any] = {}
    if dados.marca_modelo:
        out["modelo"] = dados.marca_modelo
        marca, _, _resto = dados.marca_modelo.partition("/")
        if marca.strip():
            out["marca"] = marca.strip()
    if dados.ano is not None:
        out["ano"] = dados.ano
    if dados.cor:
        out["cor"] = dados.cor
    if dados.chassi:
        out["chassi"] = dados.chassi
    if dados.renavam:
        out["renavam"] = dados.renavam
    if dados.nome_proprietario:
        out["proprietario_registrado"] = dados.nome_proprietario
    if dados.placa:
        out["placa"] = dados.placa
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
