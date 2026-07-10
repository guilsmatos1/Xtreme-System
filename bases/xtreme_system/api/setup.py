"""FastAPI app initialization, middlewares, and error handlers."""

import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path
from typing import Any

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

logger = logging.getLogger(__name__)

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class _RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


logger.addFilter(_RequestIDFilter())

app = FastAPI(title="Xtreme Motors")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _request_id(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    token = request_id_ctx.set(rid)
    response = await call_next(request)
    request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


@app.middleware("http")
async def _log_errors(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    try:
        return await call_next(request)
    except Exception:
        logger.exception("unhandled error request=%s", request.url)
        raise


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
    logger.exception("unhandled error at %s", request.url)
    if request.url.path.startswith("/ui/"):
        return HTMLResponse("<p>Erro interno. Contate suporte.</p>", status_code=500)
    return JSONResponse({"detail": "Erro interno do servidor"}, status_code=500)
