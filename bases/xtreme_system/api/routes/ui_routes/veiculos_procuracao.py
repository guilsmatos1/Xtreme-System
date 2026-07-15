"""HTMX routes for veículo procuração."""

from typing import Annotated

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_procuracao_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import remover_orfaos, salvar_arquivos
from xtreme_system.api.setup import app
from xtreme_system.documento_procuracao import core as documento_procuracao
from xtreme_system.veiculo import core as veiculo


def _procuracao_modal(
    request: Request, session: Session, veiculo_id: int, erro: str | None = None
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    remover_orfaos(session, item.documentos_procuracao, documento_procuracao.delete)
    session.refresh(item)
    return templates.TemplateResponse(
        request,
        "_modal_procuracao_veiculo.html",
        {"veiculo": item, "erro": erro},
        status_code=400 if erro else 200,
    )


@app.get("/ui/veiculos/{veiculo_id}/procuracao")
def ui_veiculo_procuracao(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    veiculo_id: int,
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    return _procuracao_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/procuracao")
def ui_veiculo_procuracao_upload(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    veiculo_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    _found(veiculo.get(session, veiculo_id), "Veículo")
    erro = _validar_uploads(documentos)
    if erro:
        return _procuracao_modal(request, session, veiculo_id, erro)
    salvar_arquivos(
        session,
        upload_dir=_uploads_procuracao_dir(veiculo_id),
        url_prefix=f"/static/uploads/veiculos/{veiculo_id}/procuracao",
        create_fn=documento_procuracao.create,
        schema=documento_procuracao.DocumentoProcuracaoCreate,
        fk_field="veiculo_id",
        fk_id=veiculo_id,
        arquivos=documentos,
    )
    return _procuracao_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/procuracao/{doc_id}/excluir")
def ui_veiculo_procuracao_excluir(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    veiculo_id: int,
    doc_id: int,
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    doc = _found(documento_procuracao.get(session, doc_id), "Documento")
    if doc.veiculo_id != veiculo_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    documento_procuracao.delete(session, doc)
    path = _uploaded_file_path(doc.url or "")
    if path is not None:
        _remover_upload(path)
    return _procuracao_modal(request, session, veiculo_id)
