"""HTMX route for veículo cliente vendedor."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import (
    SessionDep,
    found,
    require_operacao,
    templates,
)
from xtreme_system.api.setup import app
from xtreme_system.compra import core as compra
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
    item = found(veiculo.get(session, veiculo_id), "Veículo")
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    if item_compra is not None:
        session.refresh(item_compra.cliente)
    return templates.TemplateResponse(
        request,
        "_modal_cliente_vendedor.html",
        {
            "veiculo": item,
            "user": user,
            "compra": item_compra,
            "erro": erro,
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
    return _cliente_vendedor_modal(request, session, user, veiculo_id)
