"""HTMX routes for vendas."""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

from xtreme_system.api.deps import templates
from xtreme_system.api.route_factories import _sort_key, register_crud_ui_routes
from xtreme_system.api.routes.workflows import validate_cliente_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)

# ---- Vendas (UI) ----


def _ctx_form_venda(session: Session) -> dict[str, Any]:
    veiculos = veiculo.list_all(session)
    veiculos_disponiveis = [
        v for v in veiculos if v.status == veiculo.StatusVeiculo.disponivel
    ]
    return {
        "clientes": cliente.list_all(session),
        "veiculos": veiculos_disponiveis,
        "status": list(venda.StatusVenda),
    }


def _parse_venda_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("valor_entrada") == "":
        data["valor_entrada"] = None
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if not data.get("data_venda"):
        data["data_venda"] = str(datetime.now(UTC).date())
    return data


register_crud_ui_routes(
    app,
    templates,
    venda,
    "/ui/vendas",
    "Venda",
    create_schema=venda.VendaCreate,
    update_schema=venda.VendaUpdate,
    list_key="vendas",
    item_key="venda",
    list_template="vendas.html",
    list_partial_template="_linhas_vendas.html",
    ok_partial_template="_vendas_ok.html",
    form_template="_form_venda.html",
    ctx_form=_ctx_form_venda,
    parse_form=_parse_venda_form,
    before_create=validate_cliente_veiculo_fks,
    before_update=validate_cliente_veiculo_fks,
    after_create=whatsapp.notificar_venda,
    sort_fields={
        "cliente": lambda v: _sort_key(v.cliente.nome),
        "veiculo": lambda v: _sort_key(v.veiculo.modelo),
        "data": "data_venda",
        "valor": "valor_venda",
        "entrada": "valor_entrada",
        "pagamento": "forma_pagamento",
        "parcelas": "parcelas",
        "status": "status",
    },
    csv_filename="vendas.csv",
    csv_headers=[
        "ID",
        "Cliente",
        "Veiculo",
        "Data",
        "Valor Venda",
        "Valor Entrada",
        "Forma Pagamento",
        "Parcelas",
        "Status",
        "Observacoes",
    ],
    csv_row=lambda v: [
        v.id,
        v.cliente.nome,
        f"{v.veiculo.modelo} ({v.veiculo.placa})",
        v.data_venda.isoformat(),
        f"{v.valor_venda:.2f}",
        f"{v.valor_entrada:.2f}" if v.valor_entrada is not None else "",
        v.forma_pagamento,
        v.parcelas,
        v.status.value,
        v.observacoes or "",
    ],
)
