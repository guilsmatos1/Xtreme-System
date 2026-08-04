"""HTMX routes for integração RSD (puxar dados + consulta unitária)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response

from xtreme_system.api.deps import SessionDep, require_operacao, templates
from xtreme_system.database.core import detach_request_session
from xtreme_system.rsd import core as rsd
from xtreme_system.usuario import core as usuario

router = APIRouter()


def _status_partial(
    request: Request,
    *,
    erro: str | None = None,
    sucesso: str | None = None,
    unitaria: rsd.UnitariaResult | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_rsd_status.html",
        {
            "erro": erro,
            "sucesso": sucesso,
            "unitaria": unitaria,
        },
        status_code=status_code,
    )


@router.post("/ui/rsd/puxar-dados")
def ui_rsd_puxar_dados(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
) -> HTMLResponse:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return _status_partial(request, erro=str(exc), status_code=400)

    detach_request_session(request, keep=(user, config))
    try:
        with client:
            dados = client.puxar_dados(placa)
    except rsd.RsdError as exc:
        return _status_partial(request, erro=str(exc), status_code=400)

    campos = rsd.mapear_para_veiculo(dados)
    return templates.TemplateResponse(
        request,
        "_rsd_status.html",
        {
            "sucesso": "Dados carregados do RSD.",
            "campos": campos,
            "erro": None,
            "unitaria": None,
        },
    )


@router.post("/ui/rsd/consulta-unitaria")
def ui_rsd_consulta_unitaria(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
) -> HTMLResponse:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdNotConfiguredError as exc:
        return _status_partial(request, erro=str(exc), status_code=400)

    detach_request_session(request, keep=(user, config))
    try:
        with client:
            resultado = client.consultar_unitaria_be(placa)
    except rsd.RsdError as exc:
        return _status_partial(request, erro=str(exc), status_code=400)

    return _status_partial(
        request,
        sucesso=resultado.status_display or "Consulta concluída.",
        unitaria=resultado,
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
