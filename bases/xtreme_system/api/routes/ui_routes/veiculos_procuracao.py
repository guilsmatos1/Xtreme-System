"""HTMX routes for veículo procuração."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from xtreme_system.api.deps import require_operacao
from xtreme_system.api.routes.ui_routes.attachment_routes import (
    AttachmentRouteConfig,
    callback_from,
    register_attachment_routes,
)
from xtreme_system.api.routes.ui_routes.upload_paths import (
    _uploads_procuracao_dir,
)
from xtreme_system.documento_procuracao import core as documento_procuracao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

router = APIRouter()

_AbrirProcuracaoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "abrir_procuracao"))
]
_EnviarProcuracaoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "enviar_procuracao"))
]
_ExcluirProcuracaoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "excluir_procuracao"))
]


def _get_veiculo(session: Any, item_id: int) -> Any:
    return veiculo.get(session, item_id)


def _get_uploads_procuracao_dir(item_id: int) -> Any:
    return _uploads_procuracao_dir(item_id)


register_attachment_routes(
    router,
    AttachmentRouteConfig(
        name="veiculo_procuracao",
        path="/ui/veiculos/{veiculo_id}/procuracao",
        parent_param="veiculo_id",
        attachment_param="doc_id",
        parent_loader=_get_veiculo,
        attachment_loader=callback_from(globals(), "documento_procuracao.get"),
        parent_label="Veículo",
        parent_context_key="veiculo",
        template="_modal_procuracao_veiculo.html",
        upload_dir=_get_uploads_procuracao_dir,
        url_prefix=lambda item_id: f"/static/uploads/veiculos/{item_id}/procuracao",
        create_fn=callback_from(globals(), "documento_procuracao.create"),
        schema=documento_procuracao.DocumentoProcuracaoCreate,
        fk_field="veiculo_id",
        delete_fn=callback_from(globals(), "documento_procuracao.delete"),
        upload_field="documentos",
        attachment_label="Documento",
        get_dependency=_AbrirProcuracaoDep,
        upload_dependency=_EnviarProcuracaoDep,
        delete_dependency=_ExcluirProcuracaoDep,
    ),
)
