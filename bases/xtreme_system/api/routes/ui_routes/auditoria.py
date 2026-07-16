"""HTMX routes for auditoria."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode

import structlog
from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import _csv_response
from xtreme_system.api.setup import app
from xtreme_system.auditoria import core as auditoria
from xtreme_system.usuario import core as usuario

logger = structlog.get_logger(__name__)

# ---- Auditoria (consulta, admin-only) ----


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


def _ctx_auditoria(
    session: Session,
    user: usuario.Usuario,
    *,
    usuario_id: int | None,
    tabela: str | None,
    tipo_acao: str | None,
    data_de: date | None,
    data_ate: date | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    registros = auditoria.query(
        session,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
        limit=limit,
        offset=offset,
    )
    total = auditoria.count(
        session,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
    )
    filtros: dict[str, Any] = {}
    if data_de is not None:
        filtros["data_de"] = data_de.isoformat()
    if data_ate is not None:
        filtros["data_ate"] = data_ate.isoformat()
    if usuario_id is not None:
        filtros["usuario_id"] = usuario_id
    if tabela:
        filtros["tabela"] = tabela
    if tipo_acao:
        filtros["tipo_acao"] = tipo_acao
    return {
        "user": user,
        "registros": registros,
        "nomes_usuarios": _nomes_usuarios(session, registros),
        "usuarios": usuario.list_all(session),
        "tabelas": auditoria.tabelas(session),
        "tipos": auditoria.TIPO_ACOES,
        "f_usuario_id": usuario_id,
        "f_tabela": tabela,
        "f_tipo_acao": tipo_acao,
        "f_data_de": data_de,
        "f_data_ate": data_ate,
        "filtros_qs": urlencode(filtros),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/ui/auditoria")
def ui_auditoria(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    usuario_id: int | None = None,
    tabela: str | None = None,
    tipo_acao: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    if data_de is None:
        data_de = datetime.now(UTC).date() - timedelta(days=1)
    if data_ate is None:
        data_ate = datetime.now(UTC).date()
    ctx = _ctx_auditoria(
        session,
        user,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
        limit=limit,
        offset=offset,
    )
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_auditoria_resultado.html", ctx)
    return templates.TemplateResponse(request, "auditoria.html", ctx)


@app.get("/ui/auditoria/exportar")
def ui_auditoria_exportar(
    session: SessionDep,
    _: UIAdmin,
    usuario_id: int | None = None,
    tabela: str | None = None,
    tipo_acao: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
) -> Response:
    # Teto de 10k linhas no export; paginar se crescer além disso.
    registros = auditoria.query(
        session,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
        limit=10_000,
        offset=0,
    )
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
