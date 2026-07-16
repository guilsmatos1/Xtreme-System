"""HTMX routes for compras."""

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import _sort_key, register_crud_ui_routes
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_compra_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import remover_orfaos, salvar_arquivos
from xtreme_system.api.routes.workflows import validate_cliente_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.imagem_comprovante_compra import core as imagem_comprovante_compra
from xtreme_system.veiculo import core as veiculo

logger = structlog.get_logger(__name__)


def _ctx_form_compra(session: Session) -> dict[str, Any]:
    return {
        "clientes": cliente.list_all(session),
        "veiculos": veiculo.list_all(session),
    }


def _parse_compra_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("debitos") == "":
        data["debitos"] = None
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if not data.get("data_compra"):
        data["data_compra"] = str(datetime.now(UTC).date())
    return data


def _ctx_lista_compras(
    session: Session, compras: list[compra.Compra]
) -> dict[str, Any]:
    return {
        "comprovantes_por_compra": {
            item.id: imagem_comprovante_compra.list_by_compra(session, item.id)
            for item in compras
        }
    }


def _remover_arquivos_comprovantes(session: Session, obj: compra.Compra) -> None:
    for comprovante in imagem_comprovante_compra.list_by_compra(session, obj.id):
        path = _uploaded_file_path(comprovante.url or "")
        if path is not None:
            _remover_upload(path)


def _comprovantes_modal(
    request: Request,
    session: Session,
    compra_id: int,
    erro: str | None = None,
    *,
    action_oob: bool = False,
) -> HTMLResponse:
    item = _found(compra.get(session, compra_id), "Compra")
    comprovantes = imagem_comprovante_compra.list_by_compra(session, compra_id)
    remover_orfaos(session, comprovantes, imagem_comprovante_compra.delete)
    comprovantes = imagem_comprovante_compra.list_by_compra(session, compra_id)
    return templates.TemplateResponse(
        request,
        "_modal_comprovantes_compra.html",
        {
            "compra": item,
            "comprovantes": comprovantes,
            "erro": erro,
            "action_oob": action_oob,
        },
        status_code=400 if erro else 200,
    )


@app.get("/ui/compras/{compra_id}/comprovantes")
def ui_compra_comprovantes(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    compra_id: int,
) -> HTMLResponse:
    return _comprovantes_modal(request, session, compra_id)


@app.post("/ui/compras/{compra_id}/comprovantes")
def ui_compra_comprovantes_upload(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    compra_id: int,
    comprovantes: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    _found(compra.get(session, compra_id), "Compra")
    erro = _validar_uploads(comprovantes)
    if erro:
        return _comprovantes_modal(request, session, compra_id, erro)

    salvar_arquivos(
        session,
        upload_dir=_uploads_compra_dir(compra_id),
        url_prefix=f"/static/uploads/compras/{compra_id}/comprovantes",
        create_fn=imagem_comprovante_compra.create,
        schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
        fk_field="compra_id",
        fk_id=compra_id,
        arquivos=comprovantes,
    )
    return _comprovantes_modal(request, session, compra_id, action_oob=True)


@app.post("/ui/compras/{compra_id}/comprovantes/{comprovante_id}/excluir")
def ui_compra_comprovantes_excluir(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    compra_id: int,
    comprovante_id: int,
) -> HTMLResponse:
    comprovante = _found(
        imagem_comprovante_compra.get(session, comprovante_id), "Comprovante"
    )
    if comprovante.compra_id != compra_id:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    imagem_comprovante_compra.delete(session, comprovante)
    path = _uploaded_file_path(comprovante.url or "")
    if path is not None:
        _remover_upload(path)
    return _comprovantes_modal(request, session, compra_id, action_oob=True)


register_crud_ui_routes(
    app,
    templates,
    compra,
    "/ui/compras",
    "Compra",
    create_schema=compra.CompraCreate,
    update_schema=compra.CompraUpdate,
    list_key="compras",
    item_key="compra",
    list_template="compras.html",
    list_partial_template="_linhas_compras.html",
    ok_partial_template="_compras_ok.html",
    form_template="_form_compra.html",
    ctx_form=_ctx_form_compra,
    ctx_list=_ctx_lista_compras,
    parse_form=_parse_compra_form,
    before_create=validate_cliente_veiculo_fks,
    before_update=validate_cliente_veiculo_fks,
    before_delete=_remover_arquivos_comprovantes,
    sort_fields={
        "cliente": lambda c: _sort_key(c.cliente.nome),
        "veiculo": lambda c: _sort_key(c.veiculo.modelo),
        "data": "data_compra",
        "valor": "valor_compra",
        "debitos": "debitos",
    },
    csv_filename="compras.csv",
    csv_headers=[
        "ID",
        "Cliente",
        "Veiculo",
        "Data",
        "Valor Compra",
        "Debitos",
        "Observacoes",
    ],
    csv_row=lambda c: [
        c.id,
        c.cliente.nome,
        f"{c.veiculo.modelo} ({c.veiculo.placa})",
        c.data_compra.isoformat(),
        f"{c.valor_compra:.2f}",
        f"{c.debitos:.2f}" if c.debitos is not None else "",
        c.observacoes or "",
    ],
    register_create=False,
)
