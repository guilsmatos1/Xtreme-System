"""FastAPI app initialization, middlewares, and error handlers."""

import math
import os
import time
import uuid
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles

from xtreme_system.api.deps import (
    _NaoAdminError,
    _NaoAutenticadoError,
    _NaoAutorizadoError,
)
from xtreme_system.database.core import DatabaseRateLimiterStore, RateLimiterStore
from xtreme_system.logging.core import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)

_MAX_REQUEST_BYTES = 20 * 1024 * 1024  # 20 MB

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


class _MemoryRateLimiterStore:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def allow(
        self, bucket: str, limit: int, window_seconds: float
    ) -> tuple[bool, float]:
        now = time.time()
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


_rate_limit_store_state: dict[str, RateLimiterStore | None] = {"store": None}


def _get_rate_limit_store() -> RateLimiterStore:
    store = _rate_limit_store_state["store"]
    if store is None:
        if os.environ.get("RATE_LIMIT_STORE", "database").lower() == "memory":
            store = _MemoryRateLimiterStore()
        else:
            store = DatabaseRateLimiterStore()
        _rate_limit_store_state["store"] = store
    return store


def configure_rate_limit_store(store: RateLimiterStore) -> None:
    _rate_limit_store_state["store"] = store


def _cors_origins() -> list[str]:
    # Lê env direto para não acoplar setup.py a Settings (que exige
    # AUTH_SECRET_KEY) durante o import do conftest de testes.
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:8000")
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="Xtreme Motors")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
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
        raise
    structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = rid
    return response


@app.middleware("http")
async def _limite_request_size(
    request: Request, call_next: Callable[[Request], Any]
) -> Any:
    cl = request.headers.get("content-length")
    if cl and int(cl) > _MAX_REQUEST_BYTES:
        return Response("Request excede 20 MB", status_code=413)
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
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",", 1)[0].strip()
        if client_ip:
            return client_ip
    return request.client.host if request.client else "desconhecido"


@app.middleware("http")
async def _rate_limit(request: Request, call_next: Callable[[Request], Any]) -> Any:
    path = request.url.path
    if path.startswith("/static/") or path in _ROTAS_ISENTAS_RATE_LIMIT:
        return await call_next(request)

    client_ip = _client_ip(request)
    store = _get_rate_limit_store()

    if request.method == "POST" and path.endswith("/login"):
        allowed, retry_after = store.allow(
            f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS
        )
        if not allowed:
            return _rate_limit_response(
                request,
                "Muitas tentativas de login. Tente novamente em instantes.",
                retry_after,
            )
        return await call_next(request)

    allowed, retry_after = store.allow(client_ip, _GERAL_LIMIT, _GERAL_WINDOW_SECONDS)
    if not allowed:
        return _rate_limit_response(
            request,
            "Muitas requisições. Tente novamente em instantes.",
            retry_after,
        )
    return await call_next(request)


_ui_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_ui_dir / "static"), name="static")


@app.get("/")
def raiz() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.exception_handler(_NaoAutenticadoError)
def _handle_nao_autenticado(
    _request: Request, _exc: _NaoAutenticadoError
) -> RedirectResponse:
    return RedirectResponse("/ui/login", status_code=303)


@app.exception_handler(_NaoAdminError)
def _handle_nao_admin(_request: Request, _exc: _NaoAdminError) -> HTMLResponse:
    return HTMLResponse("<p>Requer papel admin</p>", status_code=403)


@app.exception_handler(_NaoAutorizadoError)
def _handle_nao_autorizado(
    _request: Request, _exc: _NaoAutorizadoError
) -> HTMLResponse:
    return HTMLResponse(
        "<p>Seu perfil não tem acesso a esta página.</p>", status_code=403
    )


@app.exception_handler(Exception)
def _handle_erro_interno(request: Request, _exc: Exception) -> Response:
    logger.exception("unhandled_error", url=str(request.url))
    if request.url.path.startswith("/ui/"):
        return HTMLResponse("<p>Erro interno. Contate suporte.</p>", status_code=500)
    return JSONResponse({"detail": "Erro interno do servidor"}, status_code=500)
