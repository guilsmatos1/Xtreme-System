"""HTMX routes for veículo comprovantes de compra."""

from typing import Annotated

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_compra_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import remover_orfaos, salvar_arquivos
from xtreme_system.api.setup import app
from xtreme_system.compra import core as compra
from xtreme_system.imagem_comprovante_compra import core as imagem_comprovante_compra
from xtreme_system.veiculo import core as veiculo


def _comprovantes_modal(
    request: Request, session: Session, veiculo_id: int, erro: str | None = None
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    documentos = []
    if item_compra is not None:
        comprovantes = imagem_comprovante_compra.list_by_compra(session, item_compra.id)
        remover_orfaos(session, comprovantes, imagem_comprovante_compra.delete)
        documentos = imagem_comprovante_compra.list_by_compra(session, item_compra.id)
    return templates.TemplateResponse(
        request,
        "_modal_comprovantes_veiculo.html",
        {"veiculo": item, "documentos": documentos, "erro": erro},
        status_code=400 if erro else 200,
    )


@app.get("/ui/veiculos/{veiculo_id}/comprovantes")
def ui_veiculo_comprovantes(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
) -> HTMLResponse:
    return _comprovantes_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/comprovantes")
def ui_veiculo_comprovantes_upload(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is None:
        return _comprovantes_modal(
            request, session, veiculo_id, "Compra não encontrada para este veículo"
        )
    erro = _validar_uploads(documentos)
    if erro:
        return _comprovantes_modal(request, session, veiculo_id, erro)
    salvar_arquivos(
        session,
        upload_dir=_uploads_compra_dir(item_compra.id),
        url_prefix=f"/static/uploads/compras/{item_compra.id}/comprovantes",
        create_fn=imagem_comprovante_compra.create,
        schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
        fk_field="compra_id",
        fk_id=item_compra.id,
        arquivos=documentos,
    )
    return _comprovantes_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/comprovantes/{doc_id}/excluir")
def ui_veiculo_comprovantes_excluir(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    doc_id: int,
) -> HTMLResponse:
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is None:
        return _comprovantes_modal(
            request, session, veiculo_id, "Compra não encontrada para este veículo"
        )
    doc = _found(imagem_comprovante_compra.get(session, doc_id), "Comprovante")
    if doc.compra_id != item_compra.id:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    imagem_comprovante_compra.delete(session, doc)
    path = _uploaded_file_path(doc.url or "")
    if path is not None:
        _remover_upload(path)
    return _comprovantes_modal(request, session, veiculo_id)
