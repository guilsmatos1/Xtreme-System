"""HTMX routes for clientes."""

from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import register_crud_ui_routes
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.venda import core as venda

logger = structlog.get_logger(__name__)

# ---- Clientes (UI) ----


def _ctx_form_cliente(_session: Session) -> dict[str, Any]:
    return {"tipos": list(cliente.TipoCliente)}


def _veiculos_modal(
    request: Request, session: Session, cliente_id: int
) -> HTMLResponse:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    vendas = venda.list_by_cliente(session, cliente_id)
    return templates.TemplateResponse(
        request, "_modal_veiculos_cliente.html", {"cliente": item, "vendas": vendas}
    )


@app.get("/ui/clientes/{cliente_id}/veiculos")
def ui_cliente_veiculos(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    cliente_id: int,
) -> HTMLResponse:
    return _veiculos_modal(request, session, cliente_id)


register_crud_ui_routes(
    app,
    templates,
    cliente,
    "/ui/clientes",
    "Cliente",
    create_schema=cliente.ClienteCreate,
    update_schema=cliente.ClienteUpdate,
    list_key="clientes",
    item_key="cliente",
    list_template="clientes.html",
    list_partial_template="_linhas_clientes.html",
    ok_partial_template="_clientes_ok.html",
    form_template="_form_cliente.html",
    ctx_form=_ctx_form_cliente,
    searchable=True,
    sort_fields={
        "nome": "nome",
        "documento": "documento",
        "telefone": "telefone",
        "tipo": "tipo",
        "cidade": "cidade",
        "estado": "estado",
    },
    csv_filename="clientes.csv",
    csv_headers=["ID", "Nome", "CPF", "Telefone", "Tipo", "Cidade", "Estado"],
    csv_row=lambda c: [
        c.id,
        c.nome,
        c.documento,
        c.telefone or "",
        c.tipo.value,
        c.cidade or "",
        c.estado or "",
    ],
)
