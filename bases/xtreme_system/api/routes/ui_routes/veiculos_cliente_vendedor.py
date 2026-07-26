"""HTMX routes for veículo cliente vendedor (documentos do vendedor)."""

from typing import Annotated

from fastapi import Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import (
    SessionDep,
    UIAdmin,
    _found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_cliente_dir,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    excluir_anexo_entidade,
    pending_upload_paths,
    remover_orfaos,
    salvar_anexos_entidade,
)
from xtreme_system.api.setup import app
from xtreme_system.compra import core as compra
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

_AbrirClienteVendedorDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "abrir_cliente_vendedor"))
]


def _cliente_vendedor_modal(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    veiculo_id: int,
    erro: str | None = None,
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
            "user": user,
            "compra": item_compra,
            "documentos": documentos,
            "erro": erro,
            "pending_upload_paths": pending_upload_paths(session),
        },
        status_code=400 if erro else 200,
    )


@app.get("/ui/veiculos/{veiculo_id}/cliente-vendedor")
def ui_veiculo_cliente_vendedor(
    request: Request,
    session: SessionDep,
    user: _AbrirClienteVendedorDep,
    veiculo_id: int,
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    return _cliente_vendedor_modal(request, session, user, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/cliente-vendedor/documentos")
def ui_veiculo_cliente_vendedor_documentos_upload(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    veiculo_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is None:
        return _cliente_vendedor_modal(
            request, session, user, veiculo_id, "Cliente vendedor não encontrado"
        )
    erro = salvar_anexos_entidade(
        session,
        upload_dir=_uploads_cliente_dir(item_compra.cliente_id),
        url_prefix=f"/static/uploads/clientes/{item_compra.cliente_id}/documentos",
        create_fn=imagem_documento_cliente.create,
        schema=imagem_documento_cliente.ImagemDocumentoClienteCreate,
        fk_field="cliente_id",
        fk_id=item_compra.cliente_id,
        arquivos=documentos,
        actor_id=user.id,
    )
    if erro:
        return _cliente_vendedor_modal(request, session, user, veiculo_id, erro)
    return _cliente_vendedor_modal(request, session, user, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/cliente-vendedor/documentos/{doc_id}/excluir")
def ui_veiculo_cliente_vendedor_documentos_excluir(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    veiculo_id: int,
    doc_id: int,
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is None:
        return _cliente_vendedor_modal(
            request, session, user, veiculo_id, "Cliente vendedor não encontrado"
        )
    doc = _found(imagem_documento_cliente.get(session, doc_id), "Documento")
    excluir_anexo_entidade(
        session,
        anexo=doc,
        parent_field="cliente_id",
        parent_id=item_compra.cliente_id,
        delete_fn=imagem_documento_cliente.delete,
        actor_id=user.id,
        not_found_detail="Documento não encontrado",
    )
    return _cliente_vendedor_modal(request, session, user, veiculo_id)
