"""HTMX routes for veículo imagens."""

from typing import Annotated

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.ui_routes.uploads import remover_orfaos, salvar_arquivos
from xtreme_system.api.setup import app
from xtreme_system.imagem_veiculo import core as imagem_veiculo
from xtreme_system.veiculo import core as veiculo


def _imagem_modal(request: Request, session: Session, veiculo_id: int) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    remover_orfaos(session, item.imagens, imagem_veiculo.delete)
    session.refresh(item)
    return templates.TemplateResponse(
        request, "_modal_imagens_veiculo.html", {"veiculo": item}
    )


@app.get("/ui/veiculos/{veiculo_id}/imagens")
def ui_veiculo_imagens(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
) -> HTMLResponse:
    return _imagem_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/imagens")
def ui_veiculo_imagens_upload(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    imagens: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    erro = _validar_uploads(imagens)
    if erro:
        return templates.TemplateResponse(
            request,
            "_modal_imagens_veiculo.html",
            {"veiculo": item, "erro": erro},
            status_code=400,
        )
    salvar_arquivos(
        session,
        upload_dir=_uploads_dir(veiculo_id),
        url_prefix=f"/static/uploads/veiculos/{veiculo_id}",
        create_fn=imagem_veiculo.create,
        schema=imagem_veiculo.ImagemVeiculoCreate,
        fk_field="veiculo_id",
        fk_id=veiculo_id,
        arquivos=imagens,
    )
    return _imagem_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/imagens/{img_id}/excluir")
def ui_veiculo_imagens_excluir(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    img_id: int,
) -> HTMLResponse:
    img = _found(imagem_veiculo.get(session, img_id), "Imagem")
    if img.veiculo_id != veiculo_id:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    imagem_veiculo.delete(session, img)
    path = _uploaded_file_path(img.url or "")
    if path is not None:
        _remover_upload(path)
    return _imagem_modal(request, session, veiculo_id)
