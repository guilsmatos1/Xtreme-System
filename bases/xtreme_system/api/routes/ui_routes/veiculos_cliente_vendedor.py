"""HTMX routes for veículo cliente vendedor (documentos do vendedor)."""

from typing import Annotated

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_cliente_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import remover_orfaos, salvar_arquivos
from xtreme_system.api.setup import app
from xtreme_system.compra import core as compra
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.veiculo import core as veiculo


def _cliente_vendedor_modal(
    request: Request, session: Session, veiculo_id: int, erro: str | None = None
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    documentos = []
    if item_compra is not None:
        docs = list(item_compra.cliente.documentos)
        remover_orfaos(session, docs, imagem_documento_cliente.delete)
        session.refresh(item_compra.cliente)
        documentos = imagem_documento_cliente.list_by_cliente(
            session, item_compra.cliente_id
        )
    return templates.TemplateResponse(
        request,
        "_modal_cliente_vendedor.html",
        {
            "veiculo": item,
            "compra": item_compra,
            "documentos": documentos,
            "erro": erro,
        },
        status_code=400 if erro else 200,
    )


@app.get("/ui/veiculos/{veiculo_id}/cliente-vendedor")
def ui_veiculo_cliente_vendedor(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
) -> HTMLResponse:
    return _cliente_vendedor_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/cliente-vendedor/documentos")
def ui_veiculo_cliente_vendedor_documentos_upload(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is None:
        return _cliente_vendedor_modal(
            request, session, veiculo_id, "Cliente vendedor não encontrado"
        )
    erro = _validar_uploads(documentos)
    if erro:
        return _cliente_vendedor_modal(request, session, veiculo_id, erro)
    salvar_arquivos(
        session,
        upload_dir=_uploads_cliente_dir(item_compra.cliente_id),
        url_prefix=f"/static/uploads/clientes/{item_compra.cliente_id}/documentos",
        create_fn=imagem_documento_cliente.create,
        schema=imagem_documento_cliente.ImagemDocumentoClienteCreate,
        fk_field="cliente_id",
        fk_id=item_compra.cliente_id,
        arquivos=documentos,
    )
    return _cliente_vendedor_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/cliente-vendedor/documentos/{doc_id}/excluir")
def ui_veiculo_cliente_vendedor_documentos_excluir(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    doc_id: int,
) -> HTMLResponse:
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is None:
        return _cliente_vendedor_modal(
            request, session, veiculo_id, "Cliente vendedor não encontrado"
        )
    doc = _found(imagem_documento_cliente.get(session, doc_id), "Documento")
    if doc.cliente_id != item_compra.cliente_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    imagem_documento_cliente.delete(session, doc)
    path = _uploaded_file_path(doc.url or "")
    if path is not None:
        _remover_upload(path)
    return _cliente_vendedor_modal(request, session, veiculo_id)
