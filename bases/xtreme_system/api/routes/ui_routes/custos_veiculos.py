"""HTMX routes for custos de veículos."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from xtreme_system.api.deps import templates
from xtreme_system.api.route_factories import _sort_key, register_crud_ui_routes
from xtreme_system.api.setup import app
from xtreme_system.custo_veiculo import core as custo_veiculo
from xtreme_system.veiculo import core as veiculo


def _ctx_form_custo(session: Session) -> dict[str, Any]:
    return {"veiculos": veiculo.list_all(session), "hoje": datetime.now(UTC).date()}


def _ctx_list_custos(
    _session: Session, custos: list[custo_veiculo.CustoVeiculo]
) -> dict[str, Any]:
    return {
        "total_custos": sum((item.valor for item in custos), Decimal("0")),
        "quantidade_custos": len(custos),
    }


def _parse_custo_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("descricao") == "":
        data["descricao"] = None
    if not data.get("data_custo"):
        data["data_custo"] = str(datetime.now(UTC).date())
    return data


def _validar_veiculo_fk(session: Session, data: Any) -> None:
    veiculo_id = getattr(data, "veiculo_id", None)
    if veiculo_id is not None and veiculo.get(session, veiculo_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_id inválido")


register_crud_ui_routes(
    app,
    templates,
    custo_veiculo,
    "/ui/custos-veiculos",
    "Custo de veículo",
    create_schema=custo_veiculo.CustoVeiculoCreate,
    update_schema=custo_veiculo.CustoVeiculoUpdate,
    list_key="custos",
    item_key="custo",
    list_template="custos_veiculos.html",
    list_partial_template="_linhas_custos_veiculos.html",
    ok_partial_template="_custos_veiculos_ok.html",
    form_template="_form_custo_veiculo.html",
    ctx_form=_ctx_form_custo,
    ctx_list=_ctx_list_custos,
    parse_form=_parse_custo_form,
    searchable=True,
    before_create=_validar_veiculo_fk,
    before_update=_validar_veiculo_fk,
    sort_fields={
        "veiculo": lambda c: _sort_key(c.veiculo.modelo),
        "categoria": "categoria",
        "data": "data_custo",
        "valor": "valor",
    },
    csv_filename="custos_veiculos.csv",
    csv_headers=[
        "ID",
        "Veiculo",
        "Placa",
        "Categoria",
        "Data",
        "Valor",
        "Descricao",
    ],
    csv_row=lambda c: [
        c.id,
        c.veiculo.modelo,
        c.veiculo.placa,
        c.categoria,
        c.data_custo.isoformat(),
        f"{c.valor:.2f}",
        c.descricao or "",
    ],
)
