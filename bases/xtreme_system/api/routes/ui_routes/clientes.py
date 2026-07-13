"""HTMX routes for clientes."""

from typing import Any

import structlog
from sqlalchemy.orm import Session

from xtreme_system.api.deps import templates
from xtreme_system.api.route_factories import register_crud_ui_routes
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente

logger = structlog.get_logger(__name__)

# ---- Clientes (UI) ----


def _ctx_form_cliente(_session: Session) -> dict[str, Any]:
    return {"tipos": list(cliente.TipoCliente)}


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
        "tipo": "tipo",
        "cidade": "cidade",
        "estado": "estado",
        "ativo": "ativo",
    },
    csv_filename="clientes.csv",
    csv_headers=["ID", "Nome", "CPF", "Tipo", "Cidade", "Estado", "Ativo"],
    csv_row=lambda c: [
        c.id,
        c.nome,
        c.documento,
        c.tipo.value,
        c.cidade or "",
        c.estado or "",
        "sim" if c.ativo else "nao",
    ],
)
