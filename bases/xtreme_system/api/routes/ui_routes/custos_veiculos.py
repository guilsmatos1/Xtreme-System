"""HTMX routes for custos de veículos."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListingSpec, SortField
from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.routes import (
    ColumnSpec,
    CrudUIBehaviorConfig,
    CrudUIExportConfig,
    CrudUIResourceConfig,
    CrudUIRouteConfig,
    CrudUITemplateConfig,
    register_crud_ui_routes,
)
from xtreme_system.api.deps import require_operacao, templates
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
    resource=CrudUIResourceConfig(
        label="Custo de veículo",
        create_schema=custo_veiculo.CustoVeiculoCreate,
        update_schema=custo_veiculo.CustoVeiculoUpdate,
        list_key="custos",
        item_key="custo",
    ),
    templates_config=CrudUITemplateConfig(
        list_template="custos_veiculos.html",
        list_partial_template="_linhas_custos_veiculos.html",
        ok_partial_template="_custos_veiculos_ok.html",
        form_template="_form_custo_veiculo.html",
    ),
    behavior=CrudUIBehaviorConfig(
        ctx_form=_ctx_form_custo,
        ctx_list=_ctx_list_custos,
        parse_form=_parse_custo_form,
        before_create=_validar_veiculo_fk,
        before_update=_validar_veiculo_fk,
    ),
    listing=ListingSpec(
        searchable=True,
        source="query",
        query_func=custo_veiculo.query,
        search_query_func=custo_veiculo.search_query,
        sort_fields={
            "criado_em": SortField("criado_em", custo_veiculo.CustoVeiculo.criado_em),
            "veiculo": SortField(
                lambda c: _sort_key(c.veiculo.modelo), veiculo.Veiculo.modelo
            ),
            "placa": SortField(
                lambda c: _sort_key(c.veiculo.placa), veiculo.Veiculo.placa
            ),
            "categoria": SortField("categoria", custo_veiculo.CustoVeiculo.categoria),
            "data": SortField("criado_em", custo_veiculo.CustoVeiculo.criado_em),
            "valor": SortField("valor", custo_veiculo.CustoVeiculo.valor),
            "descricao": SortField(
                lambda c: _sort_key(c.descricao or ""),
                custo_veiculo.CustoVeiculo.descricao,
            ),
        },
        default_sort="criado_em",
        default_order="desc",
    ),
    export=CrudUIExportConfig(
        csv_filename="custos_veiculos.csv",
        columns=[
            ColumnSpec("id", "ID", table=False, export=lambda c: c.id),
            ColumnSpec("veiculo", "Veiculo", export=lambda c: c.veiculo.modelo),
            ColumnSpec("placa", "Placa", export=lambda c: c.veiculo.placa),
            ColumnSpec("categoria", "Categoria", export=lambda c: c.categoria),
            ColumnSpec(
                "criado_em", "Data/Hora", export=lambda c: c.criado_em.isoformat()
            ),
            ColumnSpec(
                "valor", "Valor", field="valor", export=lambda c: f"{c.valor:.2f}"
            ),
            ColumnSpec("descricao", "Descricao", export=lambda c: c.descricao or ""),
        ],
        pagina="custos-veiculos",
    ),
    routes=CrudUIRouteConfig(
        editar_dep=require_operacao("custos-veiculos", "editar"),
        excluir_dep=require_operacao("custos-veiculos", "excluir"),
    ),
)
