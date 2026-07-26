"""HTMX routes for documento do veículo."""

from typing import Annotated

from fastapi import Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, _found, require_operacao, templates
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_dir,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    excluir_anexo_entidade,
    pending_upload_paths,
    remover_orfaos,
    salvar_anexos_entidade,
)
from xtreme_system.api.setup import app
from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

_DocumentoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "upload_documento"))
]


def _documentos_modal(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    veiculo_id: int,
    erro: str | None = None,
    *,
    action_oob: bool = False,
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    remover_orfaos(session, item.documentos, documento_veiculo.delete)
    session.refresh(item)
    return templates.TemplateResponse(
        request,
        "_modal_documentos_veiculo.html",
        {
            "veiculo": item,
            "user": user,
            "erro": erro,
            "action_oob": action_oob,
            "pending_upload_paths": pending_upload_paths(session),
        },
        status_code=400 if erro else 200,
    )


@app.get("/ui/veiculos/{veiculo_id}/documentos")
def ui_veiculo_documentos(
    request: Request,
    session: SessionDep,
    user: _DocumentoDep,
    veiculo_id: int,
) -> HTMLResponse:
    return _documentos_modal(request, session, user, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/documentos")
def ui_veiculo_documentos_upload(
    request: Request,
    session: SessionDep,
    user: _DocumentoDep,
    veiculo_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    _found(veiculo.get(session, veiculo_id), "Veículo")
    erro = salvar_anexos_entidade(
        session,
        upload_dir=_uploads_dir(veiculo_id) / "documentos",
        url_prefix=f"/static/uploads/veiculos/{veiculo_id}/documentos",
        create_fn=documento_veiculo.create,
        schema=documento_veiculo.DocumentoVeiculoCreate,
        fk_field="veiculo_id",
        fk_id=veiculo_id,
        arquivos=documentos,
        actor_id=user.id,
    )
    if erro:
        return _documentos_modal(request, session, user, veiculo_id, erro)
    return _documentos_modal(request, session, user, veiculo_id, action_oob=True)


@app.post("/ui/veiculos/{veiculo_id}/documentos/{doc_id}/excluir")
def ui_veiculo_documentos_excluir(
    request: Request,
    session: SessionDep,
    user: _DocumentoDep,
    veiculo_id: int,
    doc_id: int,
) -> HTMLResponse:
    doc = _found(documento_veiculo.get(session, doc_id), "Documento")
    excluir_anexo_entidade(
        session,
        anexo=doc,
        parent_field="veiculo_id",
        parent_id=veiculo_id,
        delete_fn=documento_veiculo.delete,
        actor_id=user.id,
        not_found_detail="Documento não encontrado",
    )
    return _documentos_modal(request, session, user, veiculo_id, action_oob=True)
