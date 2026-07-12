"""FastAPI app initialization, middlewares, and error handlers."""

import uuid
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
from xtreme_system.logging.core import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)

_MAX_REQUEST_BYTES = 20 * 1024 * 1024  # 20 MB

app = FastAPI(title="Xtreme Motors")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
