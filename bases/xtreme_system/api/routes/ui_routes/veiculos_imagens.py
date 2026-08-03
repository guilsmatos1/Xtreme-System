"""HTMX routes for veículo imagens."""

from typing import Annotated, Any

from fastapi import Depends

from xtreme_system.api.deps import require_operacao
from xtreme_system.api.routes.ui_routes.attachment_routes import (
    AttachmentRouteConfig,
    callback_from,
    register_attachment_routes,
)
from xtreme_system.api.routes.ui_routes.upload_paths import uploads_dir
from xtreme_system.api.setup import app
from xtreme_system.imagem_veiculo import core as imagem_veiculo
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

_AbrirImagensDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "abrir_imagens"))
]
_EnviarImagensDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "enviar_imagens"))
]
_ExcluirImagensDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "excluir_imagens"))
]


def _get_veiculo(session: Any, item_id: int) -> Any:
    return veiculo.get(session, item_id)


def _get_uploads_dir(item_id: int) -> Any:
    return uploads_dir(item_id)


def _imagens_context(
    _session: Any, _veiculo: Any, user: usuario.Usuario
) -> dict[str, Any]:
    return {
        "pode_enviar_imagens": perfil.pode_operacao(user, "veiculos", "enviar_imagens"),
        "pode_excluir_imagens": perfil.pode_operacao(
            user, "veiculos", "excluir_imagens"
        ),
    }


register_attachment_routes(
    app,
    AttachmentRouteConfig(
        name="veiculo_imagens",
        path="/ui/veiculos/{veiculo_id}/imagens",
        parent_param="veiculo_id",
        attachment_param="img_id",
        parent_loader=_get_veiculo,
        attachment_loader=callback_from(globals(), "imagem_veiculo.get"),
        parent_label="Veículo",
        parent_context_key="veiculo",
        template="_modal_imagens_veiculo.html",
        upload_dir=_get_uploads_dir,
        url_prefix=lambda item_id: f"/static/uploads/veiculos/{item_id}",
        create_fn=callback_from(globals(), "imagem_veiculo.create"),
        schema=imagem_veiculo.ImagemVeiculoCreate,
        fk_field="veiculo_id",
        delete_fn=callback_from(globals(), "imagem_veiculo.delete"),
        upload_field="imagens",
        attachment_label="Imagem",
        get_dependency=_AbrirImagensDep,
        upload_dependency=_EnviarImagensDep,
        delete_dependency=_ExcluirImagensDep,
        extra_context=_imagens_context,
    ),
)
