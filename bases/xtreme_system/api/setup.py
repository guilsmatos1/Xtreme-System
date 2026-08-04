"""FastAPI app initialization, middlewares, and error handlers."""

import json
import math
import os
import time
import uuid
from collections import deque
from collections.abc import Callable
from html import escape
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from pathlib import Path
from threading import Lock
from typing import Any, cast

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from jwt import InvalidTokenError
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.concurrency import run_in_threadpool

from xtreme_system.api.deps import (
    NaoAdminError,
    NaoAutenticadoError,
    NaoAutorizadoError,
    SessionDep,
    UIUser,
)
from xtreme_system.api.routes import json as json_routes
from xtreme_system.api.routes import ui as ui_routes
from xtreme_system.auth import core as auth
from xtreme_system.database.core import (
    DatabaseRestoreInProgressError,
    bind_request_session,
    database_traffic_lock,
    finish_request_session,
    get_session,
)
from xtreme_system.database.rate_limit import DatabaseRateLimiterStore, RateLimiterStore
from xtreme_system.logging.core import configure_logging
from xtreme_system.upload_file.authorization import pode_acessar_upload

configure_logging()
logger = structlog.get_logger(__name__)

_MAX_REQUEST_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_RESTORE_REQUEST_BYTES = 512 * 1024 * 1024  # 512 MB
_REQUEST_SIZE_LIMITS = {
    "/ui/configuracoes/importar": _MAX_RESTORE_REQUEST_BYTES,
}
_RESTORE_PATH = "/ui/configuracoes/importar"

_LOGIN_LIMIT = 5
_LOGIN_WINDOW_SECONDS = 60.0
_GERAL_LIMIT = 100
_GERAL_WINDOW_SECONDS = 60.0
_ROTAS_ISENTAS_RATE_LIMIT = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}
_CORS_ALLOWED_METHODS = ["GET", "POST", "PATCH", "DELETE"]
_CORS_ALLOWED_HEADERS = ["Authorization", "Content-Type"]


def _trusted_proxy_networks() -> list[IPv4Network | IPv6Network]:
    raw = os.environ.get("TRUSTED_PROXY_IPS", "")
    return [
        ip_network(item.strip(), strict=False)
        for item in raw.split(",")
        if item.strip()
    ]


def _is_trusted_proxy(peer_host: str | None) -> bool:
    if not peer_host:
        return False
    try:
        peer_ip = ip_address(peer_host)
    except ValueError:
        return False
    return any(peer_ip in network for network in _trusted_proxy_networks())


class _MemoryRateLimiterStore:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._last_cleanup = 0.0

    def allow(
        self, bucket: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]:
        now = time.time()
        self._cleanup_old_buckets(now, window_seconds)
        hits = self._hits.pop(bucket, deque())
        cutoff = now - window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            if hits:
                self._hits[bucket] = hits
            return False, window_seconds - (now - hits[0])
        hits.append(now)
        self._hits[bucket] = hits
        return True, 0.0

    def reset(self) -> None:
        self._hits.clear()
        self._last_cleanup = 0.0

    def _cleanup_old_buckets(self, now: float, window_seconds: float) -> None:
        cleanup_interval = max(window_seconds, 60.0)
        if now - self._last_cleanup < cleanup_interval:
            return
        self._last_cleanup = now
        cutoff = now - window_seconds
        for bucket, hits in list(self._hits.items()):
            while hits and hits[0] < cutoff:
                hits.popleft()
            if not hits:
                del self._hits[bucket]


_rate_limit_store_state: dict[str, RateLimiterStore | None] = {"store": None}
_rate_limit_store_lock = Lock()


def _get_rate_limit_store() -> RateLimiterStore:
    store = _rate_limit_store_state["store"]
    if store is not None:
        return store

    with _rate_limit_store_lock:
        store = _rate_limit_store_state["store"]
        if store is None:
            if os.environ.get("RATE_LIMIT_STORE", "database").lower() == "memory":
                store = _MemoryRateLimiterStore()
            else:
                store = DatabaseRateLimiterStore()
            _rate_limit_store_state["store"] = store
    return store


def configure_rate_limit_store(store: RateLimiterStore) -> None:
    with _rate_limit_store_lock:
        _rate_limit_store_state["store"] = store


def _cors_origins() -> list[str]:
    # Lê env direto para não acoplar setup.py a Settings (que exige
    # AUTH_SECRET_KEY) durante o import do conftest de testes.
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:8000")
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]


class _APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"


def _docs_url() -> str | None:
    if _APISettings().environment.strip().lower() == "production":
        return None
    return "/docs"


_HTMX_SUCCESS_EVENTS = {
    "htmx:toast": {"message": "Alterações salvas com sucesso.", "variant": "success"},
    "htmx:close-modal": {},
}


async def _htmx_write_feedback(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    response = await call_next(request)
    is_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    is_htmx_ui = request.url.path.startswith("/ui/") and request.headers.get(
        "HX-Request"
    )
    is_success_html = (
        status.HTTP_200_OK <= response.status_code < status.HTTP_300_MULTIPLE_CHOICES
        and response.headers.get("content-type", "").startswith("text/html")
    )
    if (
        is_write
        and is_htmx_ui
        and is_success_html
        and "HX-Trigger" not in response.headers
    ):
        response.headers["HX-Trigger"] = json.dumps(_HTMX_SUCCESS_EVENTS)
    return response


def _warn_proxy_headers_without_trusted_proxies() -> None:
    if os.environ.get("FORWARDED_ALLOW_IPS") and not os.environ.get(
        "TRUSTED_PROXY_IPS"
    ):
        logger.warning(
            "trusted_proxy_ips_empty",
            message=(
                "FORWARDED_ALLOW_IPS esta configurado, mas TRUSTED_PROXY_IPS esta "
                "vazio; X-Forwarded-For sera ignorado pelo rate limit."
            ),
        )


async def _database_session(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    if request.url.path == "/health" or get_session in request.app.dependency_overrides:
        return await call_next(request)
    bind_request_session(request)
    try:
        response = await call_next(request)
    except Exception as exc:
        finish_request_session(request, exc)
        raise
    finish_request_session(request)
    return response


async def _database_restore_guard(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    if request.url.path == _RESTORE_PATH:
        return await call_next(request)
    try:
        with database_traffic_lock():
            return await call_next(request)
    except DatabaseRestoreInProgressError:
        return HTMLResponse(
            "<p>O banco está sendo restaurado. Tente novamente em instantes.</p>",
            status_code=503,
            headers={"Retry-After": "5"},
        )


async def _request_context(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    """Liga request_id ao contexto de log e loga erros não tratados.

    Precisa ser um único middleware: BaseHTTPMiddleware roda cada camada
    de middleware em uma task própria, então contextvars ligadas aqui não
    seriam visíveis a um middleware de log separado mais externo.
    """
    rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    structlog.contextvars.bind_contextvars(request_id=rid)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_error", url=str(request.url))
        if request.url.path.startswith("/ui/"):
            response = HTMLResponse(
                "<p>Erro interno. Contate suporte.</p>", status_code=500
            )
        else:
            response = JSONResponse(
                {"detail": "Erro interno do servidor"}, status_code=500
            )
        response.headers["X-Request-ID"] = rid
        return response
    else:
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        structlog.contextvars.clear_contextvars()


async def _limite_request_size(
    request: Request, call_next: Callable[[Request], Any]
) -> Any:
    cl = request.headers.get("content-length")
    max_bytes = _REQUEST_SIZE_LIMITS.get(request.url.path, _MAX_REQUEST_BYTES)
    if cl and int(cl) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        return Response(f"Request excede {max_mb} MB", status_code=413)
    return await call_next(request)


def reset_rate_limiters() -> None:
    """Limpa o estado dos limiters (usado em testes, que reusam o `app`)."""
    _get_rate_limit_store().reset()


def _rate_limit_response(request: Request, mensagem: str, retry_after: float) -> Any:
    headers = {"Retry-After": str(max(1, math.ceil(retry_after)))}
    if request.url.path.startswith("/ui/"):
        return HTMLResponse(f"<p>{mensagem}</p>", status_code=429, headers=headers)
    return JSONResponse({"detail": mensagem}, status_code=429, headers=headers)


def _client_ip(request: Request) -> str:
    peer_host = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and _is_trusted_proxy(peer_host):
        client_ip = forwarded_for.split(",", 1)[0].strip()
        if client_ip:
            return client_ip
    return peer_host or "desconhecido"


def _rate_limit_bucket(request: Request, client_ip: str) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            dados = auth.decode_token(token)
        except InvalidTokenError:
            pass
        else:
            return f"user:{dados.username}"

    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            dados = auth.decode_token(access_token)
        except InvalidTokenError:
            pass
        else:
            return f"user:{dados.username}"

    return f"ip:{client_ip}"


async def _rate_limit(
    request: Request,
    call_next: Callable[[Request], Any],
    configured_store: RateLimiterStore | None = None,
) -> Any:
    path = request.url.path
    if path.startswith("/static/") or path in _ROTAS_ISENTAS_RATE_LIMIT:
        return await call_next(request)

    client_ip = _client_ip(request)
    store = configured_store or _get_rate_limit_store()

    if request.method == "POST" and path.endswith("/login"):
        allowed, retry_after = await run_in_threadpool(
            store.allow, f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS
        )
        if not allowed:
            return _rate_limit_response(
                request,
                "Muitas tentativas de login. Tente novamente em instantes.",
                retry_after,
            )
        return await call_next(request)

    bucket = _rate_limit_bucket(request, client_ip)
    allowed, retry_after = await run_in_threadpool(
        store.allow, bucket, _GERAL_LIMIT, _GERAL_WINDOW_SECONDS
    )
    if not allowed:
        return _rate_limit_response(
            request,
            "Muitas requisições. Tente novamente em instantes.",
            retry_after,
        )
    return await call_next(request)


_ui_dir = Path(__file__).parent


def uploads_autenticados(path: str, session: SessionDep, user: UIUser) -> FileResponse:
    uploads_root = (_ui_dir / "static" / "uploads").resolve()
    file_path = (uploads_root / path).resolve()
    if not file_path.is_relative_to(uploads_root) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if not pode_acessar_upload(session, user, f"/static/uploads/{path}"):
        raise NaoAutorizadoError
    return FileResponse(file_path)


def raiz() -> RedirectResponse:
    return RedirectResponse("/ui/dashboard")


def _handle_nao_autenticado(request: Request, _exc: Exception) -> Response:
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": "/ui/login"})
    return RedirectResponse("/ui/login", status_code=303)


def _handle_http_exception(request: Request, exc: Exception) -> Response:
    exc = cast(HTTPException, exc)
    if request.url.path.startswith("/ui/"):
        return HTMLResponse(
            escape(str(exc.detail)),
            status_code=exc.status_code,
            headers=exc.headers,
        )
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers=exc.headers,
    )


def _handle_nao_admin(_request: Request, _exc: Exception) -> HTMLResponse:
    return HTMLResponse("<p>Requer papel admin</p>", status_code=403)


def _handle_nao_autorizado(_request: Request, _exc: Exception) -> HTMLResponse:
    return HTMLResponse(
        "<p>Seu perfil não tem acesso a esta página.</p>", status_code=403
    )


def _handle_erro_interno(request: Request, _exc: Exception) -> Response:
    if request.url.path.startswith("/ui/"):
        return HTMLResponse("<p>Erro interno. Contate suporte.</p>", status_code=500)
    return JSONResponse({"detail": "Erro interno do servidor"}, status_code=500)


def create_app(
    *,
    cors_origins: list[str] | None = None,
    rate_limit_store: RateLimiterStore | None = None,
) -> FastAPI:
    application = FastAPI(title="Xtreme Motors", docs_url=_docs_url())
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins() if cors_origins is None else cors_origins,
        allow_methods=_CORS_ALLOWED_METHODS,
        allow_headers=_CORS_ALLOWED_HEADERS,
    )
    application.middleware("http")(_htmx_write_feedback)
    application.router.on_startup.append(_warn_proxy_headers_without_trusted_proxies)
    application.middleware("http")(_database_session)
    application.middleware("http")(_database_restore_guard)
    application.middleware("http")(_request_context)
    application.middleware("http")(_limite_request_size)

    async def _app_rate_limit(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Any:
        return await _rate_limit(request, call_next, rate_limit_store)

    application.middleware("http")(_app_rate_limit)
    application.add_api_route(
        "/static/uploads/{path:path}", uploads_autenticados, methods=["GET"]
    )
    application.mount(
        "/static", StaticFiles(directory=_ui_dir / "static"), name="static"
    )
    application.add_api_route("/", raiz, methods=["GET"])
    application.add_exception_handler(NaoAutenticadoError, _handle_nao_autenticado)
    application.add_exception_handler(HTTPException, _handle_http_exception)
    application.add_exception_handler(NaoAdminError, _handle_nao_admin)
    application.add_exception_handler(NaoAutorizadoError, _handle_nao_autorizado)
    application.add_exception_handler(Exception, _handle_erro_interno)

    application.include_router(json_routes.router)
    for router in ui_routes.routers:
        application.include_router(router)
    return application


app = create_app()
