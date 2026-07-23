"""HTMX routes for auditoria."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast
from urllib.parse import urlencode

import structlog
from fastapi import Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BeforeValidator, Field
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import _csv_response
from xtreme_system.api.routes.ui_routes.common import (
    IdFiltro,
    PeriodoFiltro,
    TextoFiltro,
    _vazio_para_none,
)
from xtreme_system.api.setup import app
from xtreme_system.auditoria import core as auditoria
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Auditoria (consulta, admin-only) ----

LIMIT_MAX = 200
LIMIT_EXPORT = 10_000


class FiltroAuditoria(PeriodoFiltro):
    usuario_id: IdFiltro = None
    tabela: TextoFiltro = None
    tipo_acao: Annotated[
        auditoria.TipoAcao | None, BeforeValidator(_vazio_para_none)
    ] = None

    @classmethod
    def _periodo_padrao(cls) -> tuple[date, date]:
        hoje = datetime.now(UTC).date()
        return hoje - timedelta(days=1), hoje


class FiltroAuditoriaPagina(FiltroAuditoria):
    limit: int = Field(50, ge=1, le=LIMIT_MAX)
    offset: int = Field(0, ge=0)


FiltroAuditoriaDep = Annotated[FiltroAuditoria, Query()]
FiltroAuditoriaPaginaDep = Annotated[FiltroAuditoriaPagina, Query()]


def _nomes_usuarios(
    session: Session, registros: list[auditoria.Auditoria]
) -> dict[int, str]:
    ids = {r.usuario_id for r in registros if r.usuario_id is not None}
    if not ids:
        return {}
    rows = (
        session.query(usuario.Usuario.id, usuario.Usuario.username)
        .filter(usuario.Usuario.id.in_(ids))
        .all()
    )
    # cast afina Row[tuple[int,str]] para algo que dict() aceita (mypy) sem
    # gerar regra C4 do ruff.
    return dict(cast("list[tuple[int, str]]", rows))


def _query(
    session: Session, f: FiltroAuditoria, *, limit: int, offset: int
) -> list[auditoria.Auditoria]:
    data_de, data_ate = f.periodo
    return auditoria.query(
        session,
        usuario_id=f.usuario_id,
        tabela=f.tabela,
        tipo_acao=f.tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
        limit=limit,
        offset=offset,
    )


def _ctx_auditoria(
    session: Session, user: usuario.Usuario, f: FiltroAuditoriaPagina
) -> dict[str, Any]:
    data_de, data_ate = f.periodo
    registros = _query(session, f, limit=f.limit, offset=f.offset)
    total = auditoria.count(
        session,
        usuario_id=f.usuario_id,
        tabela=f.tabela,
        tipo_acao=f.tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
    )
    filtros: dict[str, Any] = {
        "data_de": data_de.isoformat(),
        "data_ate": data_ate.isoformat(),
    }
    if f.usuario_id is not None:
        filtros["usuario_id"] = f.usuario_id
    if f.tabela:
        filtros["tabela"] = f.tabela
    if f.tipo_acao:
        filtros["tipo_acao"] = f.tipo_acao
    return {
        "user": user,
        "registros": registros,
        "nomes_usuarios": _nomes_usuarios(session, registros),
        "usuarios": usuario.list_all(session),
        "tabelas": auditoria.tabelas(session),
        "tipos": auditoria.TIPO_ACOES,
        "f_usuario_id": f.usuario_id,
        "f_tabela": f.tabela,
        "f_tipo_acao": f.tipo_acao,
        "f_data_de": data_de,
        "f_data_ate": data_ate,
        "filtros_qs": urlencode(filtros),
        "total": total,
        "limit": f.limit,
        "offset": f.offset,
    }


@app.get("/ui/auditoria")
def ui_auditoria(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    filtros: FiltroAuditoriaPaginaDep,
) -> HTMLResponse:
    ctx = _ctx_auditoria(session, user, filtros)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_auditoria_resultado.html", ctx)
    return templates.TemplateResponse(request, "auditoria.html", ctx)


@app.get("/ui/auditoria/exportar")
def ui_auditoria_exportar(
    session: SessionDep,
    _: UIAdmin,
    filtros: FiltroAuditoriaDep,
) -> Response:
    # Teto de 10k linhas no export; paginar se crescer além disso.
    registros = _query(session, filtros, limit=LIMIT_EXPORT, offset=0)
    nomes = _nomes_usuarios(session, registros)
    return _csv_response(
        "auditoria.csv",
        ["ID", "Data", "Usuario", "Tabela", "Acao", "Registro"],
        [
            [
                r.id,
                r.criado_em.isoformat() if r.criado_em else "",
                nomes.get(r.usuario_id, "") if r.usuario_id else "",
                r.tabela,
                r.tipo_acao,
                r.registro_id if r.registro_id is not None else "",
            ]
            for r in registros
        ],
    )


def _pretty(dados: dict[str, Any] | None) -> str | None:
    if dados is None:
        return None
    return json.dumps(dados, indent=2, ensure_ascii=False, default=str)


@app.get("/ui/auditoria/{registro_id}/detalhe")
def ui_auditoria_detalhe(
    registro_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    reg = _found(auditoria.get(session, registro_id), "Registro de auditoria")
    nome: str | None = None
    if reg.usuario_id is not None:
        u = usuario.get(session, reg.usuario_id)
        nome = u.username if u else None
    return templates.TemplateResponse(
        request,
        "_detalhe_auditoria.html",
        {
            "reg": reg,
            "usuario_username": nome,
            "antes_json": _pretty(reg.dados_antes),
            "depois_json": _pretty(reg.dados_depois),
        },
    )
