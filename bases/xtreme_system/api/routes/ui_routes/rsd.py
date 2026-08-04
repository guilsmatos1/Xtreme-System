"""HTMX routes for integração RSD (puxar dados + consulta unitária)."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BeforeValidator, Field
from sqlalchemy.orm import Session

from xtreme_system.api.deps import (
    SessionDep,
    UIAdmin,
    found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.filters import (
    IdFiltro,
    PeriodoFiltro,
    TextoFiltro,
    vazio_para_none,
)
from xtreme_system.database.core import detach_request_session
from xtreme_system.rsd import core as rsd
from xtreme_system.usuario import core as usuario

router = APIRouter()
_RSD_STATUS_IDS = {
    "rsd-status",
    "rsd-status-compra",
    "rsd-status-consignacao",
}


def _normalize_status_id(value: str) -> str:
    return value if value in _RSD_STATUS_IDS else "rsd-status"


def _normalize_prefix(value: str) -> str:
    return value if value in {"", "vei_"} else ""


def _status_partial(
    request: Request,
    *,
    erro: str | None = None,
    sucesso: str | None = None,
    unitaria: rsd.UnitariaResult | None = None,
    status_id: str = "rsd-status",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_rsd_status.html",
        {
            "erro": erro,
            "sucesso": sucesso,
            "unitaria": unitaria,
            "status_id": _normalize_status_id(status_id),
        },
        status_code=status_code,
    )


@router.post("/ui/rsd/puxar-dados")
def ui_rsd_puxar_dados(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
    vei_placa: Annotated[str, Form()] = "",
    rsd_prefix: Annotated[str, Form()] = "",
    rsd_status_id: Annotated[str, Form()] = "rsd-status",
) -> HTMLResponse:
    placa = placa or vei_placa
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    detach_request_session(request, keep=(user, config))
    try:
        with client:
            dados = client.puxar_dados(placa)
    except rsd.RsdError as exc:
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.puxar_dados,
            placa=placa,
            usuario_id=user.id,
            sucesso=False,
            erro=str(exc),
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    campos = rsd.mapear_para_veiculo(dados, prefix=_normalize_prefix(rsd_prefix))
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.puxar_dados,
        placa=placa,
        usuario_id=user.id,
        payload=dados.model_dump(),
        campos_aplicados=campos,
        sucesso=True,
    )
    return templates.TemplateResponse(
        request,
        "_rsd_status.html",
        {
            "sucesso": "Dados carregados do RSD.",
            "campos": campos,
            "erro": None,
            "unitaria": None,
            "status_id": _normalize_status_id(rsd_status_id),
        },
    )


@router.post("/ui/rsd/consulta-unitaria")
def ui_rsd_consulta_unitaria(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
    vei_placa: Annotated[str, Form()] = "",
    rsd_status_id: Annotated[str, Form()] = "rsd-status",
) -> HTMLResponse:
    placa = placa or vei_placa
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    detach_request_session(request, keep=(user, config))
    try:
        with client:
            dossie_id = client.iniciar_unitaria(placa)
    except rsd.RsdError as exc:
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.unitaria,
            placa=placa,
            usuario_id=user.id,
            sucesso=False,
            erro=str(exc),
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.unitaria,
        placa=placa,
        usuario_id=user.id,
        sucesso=True,
        dossie_id=dossie_id,
        status_dossie="processing",
    )
    return _status_partial(
        request,
        sucesso="Consulta iniciada — aguardando o portal…",
        unitaria=rsd.UnitariaResult(
            dossie_id=dossie_id, status="processing", is_terminal=False
        ),
        status_id=rsd_status_id,
    )


@router.get("/ui/rsd/dossie/{dossie_id}/status")
def ui_rsd_dossie_status(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    dossie_id: int,
    rsd_status_id: str = "rsd-status",
) -> HTMLResponse:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    detach_request_session(request, keep=(user, config))
    try:
        with client:
            resultado = client.status_unitaria(dossie_id)
    except rsd.RsdError as exc:
        rsd.atualizar_consulta_dossie(
            dossie_id=dossie_id,
            payload=None,
            status_dossie=None,
            sucesso=False,
            erro=str(exc),
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    if resultado.is_terminal:
        rsd.atualizar_consulta_dossie(
            dossie_id=dossie_id,
            payload=resultado.model_dump(),
            status_dossie=resultado.status,
            sucesso=not bool(resultado.error),
            erro=resultado.error,
        )
    return _status_partial(
        request,
        sucesso=resultado.status_display or "Consulta em andamento…",
        unitaria=resultado,
        status_id=rsd_status_id,
    )


@router.get("/ui/rsd/dossie/{dossie_id}/pdf")
def ui_rsd_dossie_pdf(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    dossie_id: int,
) -> Response:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return HTMLResponse(str(exc), status_code=400)

    detach_request_session(request, keep=(user, config))
    try:
        with client:
            pdf = client.baixar_pdf(dossie_id)
    except rsd.RsdError as exc:
        return HTMLResponse(str(exc), status_code=400)

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="dossie-{dossie_id}.pdf"'
        },
    )


# ---- Histórico de consultas RSD (admin-only, read-only) ----

LIMIT_MAX = 200


class FiltroRsdConsulta(PeriodoFiltro):
    tipo: rsd.TipoConsultaRsd | None = None
    placa: TextoFiltro = None
    usuario_id: IdFiltro = None
    sucesso: Annotated[bool | None, BeforeValidator(vazio_para_none)] = None

    @staticmethod
    def _periodo_padrao() -> tuple[date, date]:
        hoje = datetime.now(UTC).date()
        return hoje - timedelta(days=7), hoje


class FiltroRsdConsultaPagina(FiltroRsdConsulta):
    limit: int = Field(50, ge=1, le=LIMIT_MAX)
    offset: int = Field(0, ge=0)


FiltroRsdConsultaPaginaDep = Annotated[FiltroRsdConsultaPagina, Query()]


def _nomes_usuarios(
    session: Session, registros: list[rsd.RsdConsulta]
) -> dict[int, str]:
    ids = {r.usuario_id for r in registros if r.usuario_id is not None}
    if not ids:
        return {}
    rows = (
        session.query(usuario.Usuario.id, usuario.Usuario.username)
        .filter(usuario.Usuario.id.in_(ids))
        .all()
    )
    return dict(cast("list[tuple[int, str]]", rows))


def _filtros_qs(f: FiltroRsdConsultaPagina) -> dict[str, Any]:
    filtros: dict[str, Any] = {
        "data_de": f.data_de.isoformat(),
        "data_ate": f.data_ate.isoformat(),
    }
    if f.tipo is not None:
        filtros["tipo"] = f.tipo.value
    if f.placa:
        filtros["placa"] = f.placa
    if f.usuario_id is not None:
        filtros["usuario_id"] = f.usuario_id
    if f.sucesso is not None:
        filtros["sucesso"] = str(f.sucesso).lower()
    return filtros


def _ctx_consultas(
    session: Session, user: usuario.Usuario, f: FiltroRsdConsultaPagina
) -> dict[str, Any]:
    registros = rsd.listar_consultas(
        session,
        tipo=f.tipo,
        placa=f.placa,
        usuario_id=f.usuario_id,
        sucesso=f.sucesso,
        data_de=f.data_de,
        data_ate=f.data_ate,
        limit=f.limit,
        offset=f.offset,
    )
    total = rsd.count_consultas(
        session,
        tipo=f.tipo,
        placa=f.placa,
        usuario_id=f.usuario_id,
        sucesso=f.sucesso,
        data_de=f.data_de,
        data_ate=f.data_ate,
    )
    return {
        "user": user,
        "registros": registros,
        "nomes_usuarios": _nomes_usuarios(session, registros),
        "usuarios": usuario.list_all(session),
        "f_tipo": f.tipo,
        "f_placa": f.placa,
        "f_usuario_id": f.usuario_id,
        "f_sucesso": f.sucesso,
        "f_data_de": f.data_de,
        "f_data_ate": f.data_ate,
        "filtros_qs": urlencode(_filtros_qs(f)),
        "total": total,
        "limit": f.limit,
        "offset": f.offset,
    }


@router.get("/ui/rsd/consultas")
def ui_rsd_consultas(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    filtros: FiltroRsdConsultaPaginaDep,
) -> HTMLResponse:
    ctx = _ctx_consultas(session, user, filtros)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "_rsd_consultas_resultado.html", ctx
        )
    return templates.TemplateResponse(request, "rsd_consultas.html", ctx)


def _pretty(dados: dict[str, Any] | None) -> str | None:
    if dados is None:
        return None
    return json.dumps(dados, indent=2, ensure_ascii=False, default=str)


@router.get("/ui/rsd/consultas/{consulta_id}/detalhe")
def ui_rsd_consulta_detalhe(
    consulta_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    reg = found(rsd.get_consulta(session, consulta_id), "Consulta RSD")
    nome: str | None = None
    if reg.usuario_id is not None:
        u = usuario.get(session, reg.usuario_id)
        nome = u.username if u else None
    return templates.TemplateResponse(
        request,
        "_detalhe_rsd_consulta.html",
        {
            "reg": reg,
            "usuario_username": nome,
            "payload_json": _pretty(reg.payload),
            "campos_aplicados_json": _pretty(reg.campos_aplicados),
        },
    )
