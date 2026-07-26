"""HTMX routes for veículo imagens."""

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
    salvar_anexos_entidade,
)
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


def _imagem_modal(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    veiculo_id: int,
    *,
    action_oob: bool = False,
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    session.refresh(item)
    return templates.TemplateResponse(
        request,
        "_modal_imagens_veiculo.html",
        {
            "veiculo": item,
            "action_oob": action_oob,
            "pending_upload_paths": pending_upload_paths(session),
            "pode_enviar_imagens": perfil.pode_operacao(
                user, "veiculos", "enviar_imagens"
            ),
            "pode_excluir_imagens": perfil.pode_operacao(
                user, "veiculos", "excluir_imagens"
            ),
        },
    )


@app.get("/ui/veiculos/{veiculo_id}/imagens")
def ui_veiculo_imagens(
    request: Request,
    session: SessionDep,
    user: _AbrirImagensDep,
    veiculo_id: int,
) -> HTMLResponse:
    return _imagem_modal(request, session, user, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/imagens")
def ui_veiculo_imagens_upload(
    request: Request,
    session: SessionDep,
    user: _EnviarImagensDep,
    veiculo_id: int,
    imagens: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    erro = salvar_anexos_entidade(
        session,
        upload_dir=_uploads_dir(veiculo_id),
        url_prefix=f"/static/uploads/veiculos/{veiculo_id}",
        create_fn=imagem_veiculo.create,
        schema=imagem_veiculo.ImagemVeiculoCreate,
        fk_field="veiculo_id",
        fk_id=veiculo_id,
        arquivos=imagens,
        actor_id=user.id,
    )
    if erro:
        return templates.TemplateResponse(
            request,
            "_modal_imagens_veiculo.html",
            {
                "veiculo": item,
                "erro": erro,
                "action_oob": False,
                "pode_enviar_imagens": perfil.pode_operacao(
                    user, "veiculos", "enviar_imagens"
                ),
                "pode_excluir_imagens": perfil.pode_operacao(
                    user, "veiculos", "excluir_imagens"
                ),
            },
            status_code=400,
        )
    return _imagem_modal(request, session, user, veiculo_id, action_oob=True)


@app.post("/ui/veiculos/{veiculo_id}/imagens/{img_id}/excluir")
def ui_veiculo_imagens_excluir(
    request: Request,
    session: SessionDep,
    user: _ExcluirImagensDep,
    veiculo_id: int,
    img_id: int,
) -> HTMLResponse:
    img = _found(imagem_veiculo.get(session, img_id), "Imagem")
    excluir_anexo_entidade(
        session,
        anexo=img,
        parent_field="veiculo_id",
        parent_id=veiculo_id,
        delete_fn=imagem_veiculo.delete,
        actor_id=user.id,
        not_found_detail="Imagem não encontrada",
    )
    return _imagem_modal(request, session, user, veiculo_id, action_oob=True)
