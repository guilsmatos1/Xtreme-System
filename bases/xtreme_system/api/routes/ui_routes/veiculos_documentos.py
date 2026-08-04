"""HTMX routes for documento do veículo."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from xtreme_system.api.deps import require_operacao
from xtreme_system.api.routes.ui_routes.attachment_routes import (
    AttachmentRouteConfig,
    callback_from,
    register_attachment_routes,
)
from xtreme_system.api.routes.ui_routes.upload_paths import uploads_dir
from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

router = APIRouter()

_DocumentoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "upload_documento"))
]


def _get_veiculo(session: Any, item_id: int) -> Any:
    return veiculo.get(session, item_id)


register_attachment_routes(
    router,
    AttachmentRouteConfig(
        name="veiculo_documentos",
        path="/ui/veiculos/{veiculo_id}/documentos",
        parent_param="veiculo_id",
        attachment_param="doc_id",
        parent_loader=_get_veiculo,
        attachment_loader=callback_from(globals(), "documento_veiculo.get"),
        parent_label="Veículo",
        parent_context_key="veiculo",
        template="_modal_documentos_veiculo.html",
        upload_dir=lambda item_id: uploads_dir(item_id) / "documentos",
        url_prefix=lambda item_id: f"/static/uploads/veiculos/{item_id}/documentos",
        create_fn=callback_from(globals(), "documento_veiculo.create"),
        schema=documento_veiculo.DocumentoVeiculoCreate,
        fk_field="veiculo_id",
        delete_fn=callback_from(globals(), "documento_veiculo.delete"),
        upload_field="documentos",
        attachment_label="Documento",
        get_dependency=_DocumentoDep,
        upload_dependency=_DocumentoDep,
        delete_dependency=_DocumentoDep,
    ),
)
