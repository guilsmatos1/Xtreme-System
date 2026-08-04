"""HTMX routes for veículos — CRUD override (create/update transacionais)."""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListingSpec, SortField
from xtreme_system.api.crud_ui.helpers import current_list_state
from xtreme_system.api.crud_ui.query import query_list
from xtreme_system.api.crud_ui.responses import (
    conflict_form_response,
    delete_conflict_detail,
    error_response,
    list_response,
    rollback_integrity_error_response,
    validation_error_detail,
    write_conflict_detail,
)
from xtreme_system.api.crud_ui.routes import (
    ColumnSpec,
    CrudUIBehaviorConfig,
    CrudUIExportConfig,
    CrudUIReferenceConfig,
    CrudUIResourceConfig,
    CrudUIRouteConfig,
    CrudUITemplateConfig,
    delete_list_response,
    register_crud_ui_routes,
    register_reference_lookup_routes,
)
from xtreme_system.api.crud_writes import delete_with_hook
from xtreme_system.api.deps import (
    SessionDep,
    UIUser,
    found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    pending_upload_paths,
)
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.custo_veiculo import core as custo_veiculo
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.workflow.core import validate_veiculo_fks

router = APIRouter()


def _ctx_form_veiculo(
    session: Session, veiculo_id: int | None = None
) -> dict[str, Any]:
    context = {
        "tipos": list(veiculo.TipoVeiculo),
        "tipo_entradas": list(veiculo.TipoEntrada),
        "tipos_cliente": list(cliente.TipoCliente),
    }
    if veiculo_id is not None:
        compra_atual = compra.get_latest_by_veiculo(session, veiculo_id)
        context["debitos_por_veiculo"] = (
            {veiculo_id: compra_atual.debitos} if compra_atual is not None else {}
        )
    return context


def _label_cliente(obj: cliente.Cliente) -> str:
    return f"{obj.nome} ({obj.documento})"


def _label_investidor(obj: investidor.Investidor) -> str:
    return obj.nome


def _investidores_query(session: Session) -> Any:
    return session.query(investidor.Investidor)


def _investidores_search_query(session: Session, term: str) -> Any:
    return _investidores_query(session).filter(
        investidor.Investidor.nome.ilike(f"%{term}%")
    )


_STATUS_LABELS = {
    "disponivel": "Disponível",
    "indisponivel": "Indisponível",
    "vendido": "Vendido",
    "reservado": "Reservado",
    "cancelado": "Cancelado",
}

_DEBITOS_SORT_SQL = func.coalesce(
    select(compra.Compra.debitos)
    .where(compra.Compra.veiculo_id == veiculo.Veiculo.id)
    .order_by(compra.Compra.data_compra.desc(), compra.Compra.id.desc())
    .limit(1)
    .scalar_subquery(),
    -1,
)


def _ctx_lista_veiculos(
    session: Session, veiculos: list[veiculo.Veiculo]
) -> dict[str, Any]:
    resumo = veiculo.resumo_estoque(session)
    contagens = {
        status.value: resumo.get(status, (0, Decimal("0")))[0]
        for status in veiculo.StatusVeiculo
    }
    veiculo_ids = [item.id for item in veiculos]
    debitos_por_veiculo = compra.latest_debitos_by_veiculo_ids(session, veiculo_ids)
    return {
        "total_estoque": sum(contagens.values()),
        "contagens_estoque": contagens,
        "debitos_por_veiculo": debitos_por_veiculo,
        "filtro_tipos": [(t.value, t.value.capitalize()) for t in veiculo.TipoVeiculo],
        "filtro_status": [
            (s.value, _STATUS_LABELS[s.value]) for s in veiculo.StatusVeiculo
        ],
        "filtro_tipo_entradas": [
            (t.value, t.value.capitalize()) for t in veiculo.TipoEntrada
        ],
    }


_VEICULOS_LISTING = ListingSpec(
    searchable=True,
    source="query",
    query_func=veiculo.query,
    search_query_func=veiculo.search_query,
    sort_fields={
        "modelo": SortField("modelo", veiculo.Veiculo.modelo),
        "placa": SortField("placa", veiculo.Veiculo.placa),
        "tipo": SortField("tipo", veiculo.Veiculo.tipo),
        "ano": SortField("ano", veiculo.Veiculo.ano),
        "km": SortField("km", veiculo.Veiculo.km),
        "preco": SortField("preco", veiculo.Veiculo.preco),
        "status": SortField("status", veiculo.Veiculo.status),
        "tipo_entrada": SortField("tipo_entrada", veiculo.Veiculo.tipo_entrada),
        "revisao": SortField("revisao", veiculo.Veiculo.revisao),
        "investidor": SortField("investidor", investidor.Investidor.nome),
        "procuracao": SortField("procuracao", veiculo.Veiculo.procuracao),
        "debitos": SortField("debitos", _DEBITOS_SORT_SQL),
        "tempo_estoque": SortField("criado_em", veiculo.Veiculo.criado_em),
    },
)


register_crud_ui_routes(
    router,
    templates,
    veiculo,
    "/ui/veiculos",
    resource=CrudUIResourceConfig(
        label="Veículo",
        create_schema=veiculo.VeiculoCreate,
        update_schema=veiculo.VeiculoUpdate,
        list_key="veiculos",
        item_key="veiculo",
    ),
    templates_config=CrudUITemplateConfig(
        list_template="veiculos.html",
        list_partial_template="_linhas_veiculos.html",
        ok_partial_template="_veiculos_ok.html",
        form_template="_form_veiculo.html",
    ),
    behavior=CrudUIBehaviorConfig(
        ctx_form=_ctx_form_veiculo,
        ctx_list=_ctx_lista_veiculos,
        before_create=validate_veiculo_fks,
        before_update=lambda session, data: validate_veiculo_fks(
            session, data, update=True
        ),
        before_delete=caixa.deletar_lancamento_veiculo,
        after_create=caixa.criar_lancamento_veiculo,
        after_update=caixa.sincronizar_lancamento_veiculo,
    ),
    listing=_VEICULOS_LISTING,
    export=CrudUIExportConfig(
        csv_filename="veiculos.csv",
        columns=[
            ColumnSpec("id", "ID", table=False, export=lambda v: v.id),
            ColumnSpec("modelo", "Modelo", field="modelo", export=lambda v: v.modelo),
            ColumnSpec("placa", "Placa", field="placa", export=lambda v: v.placa),
            ColumnSpec("tipo", "Tipo", field="tipo", export=lambda v: v.tipo.value),
            ColumnSpec("ano", "Ano", field="ano", export=lambda v: v.ano),
            ColumnSpec("km", "KM", field="km", export=lambda v: v.km),
            ColumnSpec(
                "preco",
                "Preco Anunciado",
                field="preco",
                export=lambda v: f"{v.preco:.2f}" if v.preco is not None else "",
            ),
            ColumnSpec(
                "status", "Estado", field="status", export=lambda v: v.status.value
            ),
            ColumnSpec(
                "tipo_entrada",
                "Tipo de Entrada",
                field="tipo_entrada",
                export=lambda v: v.tipo_entrada.value,
            ),
            ColumnSpec(
                "revisao",
                "Revisao",
                field="revisao",
                export=lambda v: "Sim" if v.revisao else "Não",
            ),
            ColumnSpec(
                "investidor",
                "Investidor",
                field="investidor",
                export=lambda v: v.investidor.nome,
            ),
            ColumnSpec(
                "procuracao",
                "Procurador",
                field="procuracao",
                export=lambda v: v.procuracao or "",
            ),
            ColumnSpec(
                "tempo_estoque",
                "Tempo de Estoque",
                field="tempo_estoque",
                export=lambda v: f"{v.tempo_estoque} dias",
            ),
        ],
        pagina="veiculos",
    ),
    routes=CrudUIRouteConfig(
        register_create=False,
        register_update=False,
        register_edit=False,
        register_delete=False,
    ),
)


register_reference_lookup_routes(
    router,
    "/ui/veiculos/referencias",
    pagina="veiculos",
    references={
        "clientes": CrudUIReferenceConfig(
            query=cliente.query,
            search_query=cliente.search_query,
            label=_label_cliente,
            campo="cliente",
        ),
        "investidores": CrudUIReferenceConfig(
            query=_investidores_query,
            search_query=_investidores_search_query,
            label=_label_investidor,
            campo="investidor",
        ),
    },
)

_EditarDep = Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))]
_ExcluirDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "excluir"))
]


@router.get("/ui/veiculos/{item_id}/editar")
def _editar_veiculo(
    item_id: int, request: Request, session: SessionDep, user: _EditarDep
) -> HTMLResponse:
    obj = found(veiculo.get(session, item_id), "Veículo")
    return templates.TemplateResponse(
        request,
        "_form_veiculo.html",
        {**_ctx_form_veiculo(session, obj.id), "veiculo": obj, "user": user},
    )


@router.get("/ui/veiculos/{item_id}/detalhes")
def _detalhe_veiculo(
    item_id: int,
    request: Request,
    session: SessionDep,
    user: UIUser,
) -> HTMLResponse:
    obj = found(veiculo.get(session, item_id), "Veículo")
    compra_atual = compra.get_latest_by_veiculo(session, item_id)
    custos = custo_veiculo.list_by_veiculo(session, item_id)
    documentos_vendedor = []
    if compra_atual is not None:
        session.refresh(compra_atual.cliente)
        documentos_vendedor = imagem_documento_cliente.list_by_cliente(
            session, compra_atual.cliente_id
        )
    return templates.TemplateResponse(
        request,
        "veiculo_detalhe.html",
        {
            "user": user,
            "veiculo": obj,
            "compra_atual": compra_atual,
            "custos": custos,
            "documentos_vendedor": documentos_vendedor,
            "pending_upload_paths": pending_upload_paths(session),
        },
    )


@router.post("/ui/veiculos/{item_id}/excluir")
def _excluir_veiculo(
    item_id: int, request: Request, session: SessionDep, user: _ExcluirDep
) -> HTMLResponse:
    obj = found(veiculo.get(session, item_id), "Veículo")
    try:
        delete_with_hook(
            veiculo,
            session,
            obj,
            caixa.deletar_lancamento_veiculo,
            user.id,
        )
    except IntegrityError:

        def build_conflict_response() -> HTMLResponse:
            return delete_list_response(
                session,
                templates,
                request,
                veiculo,
                "_linhas_veiculos.html",
                user=user,
                list_key="veiculos",
                ctx_list=_ctx_lista_veiculos,
                listing=_VEICULOS_LISTING,
                erro=delete_conflict_detail("Veículo"),
                status_code=409,
            )

        return rollback_integrity_error_response(session, build_conflict_response)
    return delete_list_response(
        session,
        templates,
        request,
        veiculo,
        "_linhas_veiculos.html",
        user=user,
        list_key="veiculos",
        ctx_list=_ctx_lista_veiculos,
        listing=_VEICULOS_LISTING,
    )


def _ok_veiculo(
    request: Request, session: Session, user: usuario.Usuario
) -> HTMLResponse:
    state = current_list_state(request)
    veiculos = query_list(session, veiculo, listing=_VEICULOS_LISTING, state=state)
    return list_response(
        templates,
        request,
        "_veiculos_ok.html",
        user=user,
        list_key="veiculos",
        lista=veiculos,
        ctx_list=_ctx_lista_veiculos(session, veiculos),
        sort=state.sort,
        order=state.order,
        q=state.q,
        search_column=state.search_column,
        limit=state.limit or 50,
        offset=state.offset,
        success=True,
    )


def _erro_veiculo(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    msg: str,
    veiculo_id: int | None = None,
) -> HTMLResponse:
    return error_response(
        templates,
        request,
        "_form_veiculo.html",
        ctx_form=_ctx_form_veiculo(session, veiculo_id),
        item_key="veiculo",
        item=None,
        erro=msg,
        status_code=400,
        user=user,
    )


@router.post("/ui/veiculos/{item_id}")
async def _atualizar_veiculo(
    item_id: int, request: Request, session: SessionDep, user: _EditarDep
) -> HTMLResponse:
    obj = found(veiculo.get(session, item_id), "Veículo")
    form = await request.form()
    dados_form: dict[str, Any] = dict(form)
    dados_form = perfil.campos_form_visiveis(user, "veiculos", dados_form)
    if perfil.pode_ver_campo(user, "veiculos", "revisao"):
        dados_form["revisao"] = dados_form.get("revisao") == "true"

    try:
        data = veiculo.VeiculoUpdate.model_validate(dados_form)
        validate_veiculo_fks(session, data, update=True)
    except (ValidationError, HTTPException) as exc:
        msg = (
            str(exc.detail)
            if isinstance(exc, HTTPException)
            else validation_error_detail(exc)
        )
        return templates.TemplateResponse(
            request,
            "_form_veiculo.html",
            {
                **_ctx_form_veiculo(session, obj.id),
                "veiculo": obj,
                "user": user,
                "erro": msg,
            },
            status_code=400,
        )

    debitos = None
    if perfil.pode_ver_campo(user, "veiculos", "debitos"):
        debitos_raw = str(form.get("debitos") or "").strip()
        if debitos_raw:
            try:
                debitos = Decimal(debitos_raw.replace(",", "."))
            except Exception:
                return _erro_veiculo(
                    request, session, user, "Débitos inválidos", item_id
                )

    try:
        atualizado = veiculo.update(session, obj, data, user.id)
        compra_atual = compra.get_latest_by_veiculo(session, atualizado.id)
        if compra_atual is not None and perfil.pode_ver_campo(
            user, "veiculos", "debitos"
        ):
            compra.update(
                session,
                compra_atual,
                compra.CompraUpdate(debitos=debitos),
                user.id,
            )
        caixa.sincronizar_lancamento_veiculo(session, atualizado, user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: conflict_form_response(
                templates,
                request,
                "_form_veiculo.html",
                ctx_form=_ctx_form_veiculo(session, obj.id),
                item_key="veiculo",
                item=obj,
                erro=write_conflict_detail("Veículo"),
                user=user,
                dados=dados_form,
            ),
        )
    return _ok_veiculo(request, session, user)
