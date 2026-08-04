"""HTMX routes for vendas."""

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Annotated, Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListingSpec, SortField
from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import (
    conflict_form_response,
    error_response,
    ok_response,
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
    register_crud_ui_routes,
    register_reference_lookup_routes,
)
from xtreme_system.api.crud_writes import safe_write
from xtreme_system.api.deps import (
    SessionDep,
    found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.upload_files import uploaded_file_path
from xtreme_system.api.routes.ui_routes.upload_paths import uploads_contrato_venda_dir
from xtreme_system.api.routes.ui_routes.venda_write import (
    VendaErro,
    preparar_venda,
)
from xtreme_system.api.routes.ui_routes.venda_write import (
    parse_venda_form as _parse_venda_form,
)
from xtreme_system.cliente import core as cliente
from xtreme_system.database.core import register_post_commit
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
from xtreme_system.empresa import core as empresa
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.investidor import core as investidor
from xtreme_system.upload_file.core import escrever_upload_atomico
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp
from xtreme_system.workflow.core import recompute_vehicle_status_on_delete

logger = structlog.get_logger(__name__)
router = APIRouter()

_CONTRATO_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="venda-contract",
)
_CONTRATO_FUTURES: set[Future[None]] = set()

# ---- Vendas (UI) ----

_CadastrarVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "cadastrar"))
]
_EditarVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "editar"))
]
_BaixarContratoVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "baixar_contrato"))
]
_VerFechamentoVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "ver_fechamento"))
]


def _ctx_form_venda(session: Session) -> dict[str, Any]:
    return {
        "status": list(venda.StatusVenda),
        "clientes": cliente.list_all(session),
        "veiculos": _veiculos_disponiveis_query(session)
        .order_by(veiculo.Veiculo.id)
        .all(),
        "tipos_cliente": list(cliente.TipoCliente),
        "tipos_veiculo": list(veiculo.TipoVeiculo),
        "investidores": investidor.list_all(session),
    }


def _veiculos_disponiveis_query(session: Session) -> Any:
    return veiculo.query(session).filter(
        veiculo.Veiculo.status == veiculo.StatusVeiculo.disponivel
    )


def _veiculos_disponiveis_search_query(session: Session, term: str) -> Any:
    return veiculo.search_query(session, term).filter(
        veiculo.Veiculo.status == veiculo.StatusVeiculo.disponivel
    )


def _label_cliente(obj: cliente.Cliente) -> str:
    return f"{obj.nome} ({obj.documento})"


def _label_veiculo(obj: veiculo.Veiculo) -> str:
    return f"{obj.placa} — {obj.modelo}"


def _ctx_lista_vendas(session: Session, _vendas: list[Any]) -> dict[str, Any]:
    return {
        "fechamentos_by_venda": fechamento_venda.ids_by_venda_ids(
            session, [item.id for item in _vendas]
        )
    }


register_crud_ui_routes(
    router,
    templates,
    venda,
    "/ui/vendas",
    resource=CrudUIResourceConfig(
        label="Venda",
        create_schema=venda.VendaCreate,
        update_schema=venda.VendaUpdate,
        list_key="vendas",
        item_key="venda",
    ),
    templates_config=CrudUITemplateConfig(
        list_template="vendas.html",
        list_partial_template="_linhas_vendas.html",
        ok_partial_template="_vendas_ok.html",
        form_template="_form_venda.html",
    ),
    behavior=CrudUIBehaviorConfig(
        ctx_form=_ctx_form_venda,
        ctx_list=_ctx_lista_vendas,
        parse_form=_parse_venda_form,
        before_delete=recompute_vehicle_status_on_delete,
    ),
    listing=ListingSpec(
        searchable=True,
        source="query",
        query_func=venda.query,
        search_query_func=venda.search_query,
        sort_fields={
            "criado_em": SortField("criado_em", venda.Venda.criado_em),
            "cliente": SortField(
                lambda v: _sort_key(v.cliente.nome), cliente.Cliente.nome
            ),
            "veiculo": SortField(
                lambda v: _sort_key(v.veiculo.modelo), veiculo.Veiculo.modelo
            ),
            "data": SortField("criado_em", venda.Venda.criado_em),
            "valor": SortField("valor_venda", venda.Venda.valor_venda),
            "entrada": SortField("valor_entrada", venda.Venda.valor_entrada),
            "divida": SortField("valor_pendente", venda.Venda.valor_pendente),
            "pagamento": SortField("forma_pagamento", venda.Venda.forma_pagamento),
            "parcelas": SortField("parcelas", venda.Venda.parcelas),
            "status": SortField("status", venda.Venda.status),
            "vendedor": SortField(
                lambda v: _sort_key(
                    (v.vendedor.nome or v.vendedor.username) if v.vendedor else ""
                ),
                usuario.Usuario.nome,
            ),
        },
        default_sort="criado_em",
        default_order="desc",
    ),
    export=CrudUIExportConfig(
        csv_filename="vendas.csv",
        columns=[
            ColumnSpec("id", "ID", table=False, export=lambda v: v.id),
            ColumnSpec(
                "cliente", "Cliente", field="cliente", export=lambda v: v.cliente.nome
            ),
            ColumnSpec(
                "veiculo",
                "Veiculo",
                field="veiculo",
                export=lambda v: f"{v.veiculo.modelo} ({v.veiculo.placa})",
            ),
            ColumnSpec(
                "criado_em",
                "Data/Hora",
                field="criado_em",
                export=lambda v: v.criado_em.isoformat(),
            ),
            ColumnSpec(
                "valor_venda",
                "Valor Venda",
                field="valor_venda",
                export=lambda v: f"{v.valor_venda:.2f}",
            ),
            ColumnSpec(
                "valor_entrada",
                "Valor Entrada",
                field="valor_entrada",
                export=lambda v: (
                    f"{v.valor_entrada:.2f}" if v.valor_entrada is not None else ""
                ),
            ),
            ColumnSpec(
                "debitos",
                "Debitos",
                field="debitos",
                export=lambda v: f"{v.debitos:.2f}" if v.debitos is not None else "",
            ),
            ColumnSpec(
                "km",
                "KM",
                field="km",
                export=lambda v: v.km if v.km is not None else "",
            ),
            ColumnSpec(
                "veiculo_troca",
                "Veiculo Troca",
                field="veiculo_troca",
                export=lambda v: (
                    f"{v.veiculo_troca.modelo} ({v.veiculo_troca.placa})"
                    if v.veiculo_troca is not None
                    else ""
                ),
            ),
            ColumnSpec(
                "valor_diferenca",
                "Valor Diferenca",
                field="valor_diferenca",
                export=lambda v: (
                    f"{v.valor_diferenca:.2f}" if v.valor_diferenca is not None else ""
                ),
            ),
            ColumnSpec(
                "pagamento_pendente",
                "Pagamento Pendente",
                field="pagamento_pendente",
                export=lambda v: "Sim" if v.pagamento_pendente else "Não",
            ),
            ColumnSpec(
                "valor_pendente",
                "Valor Pendente",
                field="valor_pendente",
                export=lambda v: (
                    f"{v.valor_pendente:.2f}" if v.valor_pendente is not None else ""
                ),
            ),
            ColumnSpec(
                "datas_pagamento",
                "Datas Pagamento",
                field="datas_pagamento",
                export=lambda v: v.datas_pagamento or "",
            ),
            ColumnSpec(
                "forma_pagamento",
                "Forma Pagamento",
                field="forma_pagamento",
                export=lambda v: v.forma_pagamento,
            ),
            ColumnSpec(
                "parcelas", "Parcelas", field="parcelas", export=lambda v: v.parcelas
            ),
            ColumnSpec(
                "status", "Status", field="status", export=lambda v: v.status.value
            ),
            ColumnSpec(
                "observacoes",
                "Observacoes",
                field="observacoes",
                export=lambda v: v.observacoes or "",
            ),
            ColumnSpec(
                "vendedor",
                "Usuario",
                field="vendedor",
                export=lambda v: (
                    (v.vendedor.nome or v.vendedor.username) if v.vendedor else ""
                ),
            ),
        ],
        pagina="vendas",
    ),
    routes=CrudUIRouteConfig(
        register_create=False,
        register_update=False,
        cadastrar_dep=require_operacao("vendas", "cadastrar"),
        editar_dep=require_operacao("vendas", "editar"),
        excluir_dep=require_operacao("vendas", "excluir"),
    ),
)


register_reference_lookup_routes(
    router,
    "/ui/vendas/referencias",
    pagina="vendas",
    references={
        "clientes": CrudUIReferenceConfig(
            query=cliente.query,
            search_query=cliente.search_query,
            label=_label_cliente,
            campo="cliente",
        ),
        "veiculos": CrudUIReferenceConfig(
            query=_veiculos_disponiveis_query,
            search_query=_veiculos_disponiveis_search_query,
            label=_label_veiculo,
            campo="veiculo",
        ),
        "veiculos-troca": CrudUIReferenceConfig(
            query=veiculo.query,
            search_query=veiculo.search_query,
            label=_label_veiculo,
            campo="veiculo_troca",
        ),
    },
)


def _ok_venda(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    *,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    vendas = venda.list_all(session, limit=limit, offset=offset)
    return ok_response(
        templates,
        request,
        "_vendas_ok.html",
        user=user,
        list_key="vendas",
        lista=vendas,
        ctx_list=_ctx_lista_vendas(session, vendas),
    )


def _erro_venda(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    msg: str,
    venda_obj: venda.Venda | None = None,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return error_response(
        templates,
        request,
        "_form_venda.html",
        ctx_form=_ctx_form_venda(session),
        item_key="venda",
        item=venda_obj,
        erro=msg,
        status_code=400,
        user=user,
        dados=dados,
    )


def _persistir_contrato_venda(
    session: Session, obj: venda.Venda, actor_id: int | None = None
) -> None:
    upload_dir = uploads_contrato_venda_dir(obj.id)
    filename = f"{uuid4().hex}.pdf"
    config_empresa = empresa.get_config(session)
    logo_path = (
        uploaded_file_path(config_empresa.logo_url) if config_empresa.logo_url else None
    )
    if logo_path is not None and not logo_path.exists():
        logo_path = None
    pdf = documento_contrato_venda.gerar_pdf(obj, config_empresa, logo_path)
    escrever_upload_atomico(session, upload_dir, filename, pdf)
    documento_contrato_venda.create(
        session,
        documento_contrato_venda.DocumentoContratoVendaCreate(
            venda_id=obj.id,
            url=f"/static/uploads/vendas/{obj.id}/contrato/{filename}",
        ),
        actor_id,
    )


def _persistir_contrato_venda_em_background(
    bind: Engine | Connection, venda_id: int, actor_id: int | None
) -> None:
    session = Session(bind=bind)
    try:
        obj = venda.get(session, venda_id)
        if obj is None:
            logger.warning("contract_sale_not_found", venda_id=venda_id)
            return
        _persistir_contrato_venda(session, obj, actor_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("contract_generation_failed", venda_id=venda_id)
    finally:
        session.close()


def _aguardar_contratos_background() -> None:
    for future in tuple(_CONTRATO_FUTURES):
        future.result()


def _agendar_persistencia_contrato_venda(
    session: Session, obj: venda.Venda, actor_id: int | None
) -> None:
    bind = session.get_bind()
    venda_id = obj.id

    def _agendar() -> None:
        future = _CONTRATO_EXECUTOR.submit(
            _persistir_contrato_venda_em_background,
            bind,
            venda_id,
            actor_id,
        )
        if isinstance(future, Future):
            _CONTRATO_FUTURES.add(future)
            future.add_done_callback(_CONTRATO_FUTURES.discard)

    register_post_commit(session, _agendar)


def _resposta_erro_preparacao_venda(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    resultado: VendaErro,
    *,
    venda_obj: venda.Venda | None = None,
) -> HTMLResponse:
    if resultado.conflito is not None:
        return conflict_form_response(
            templates,
            request,
            "_form_venda.html",
            ctx_form=_ctx_form_venda(session),
            item_key="venda",
            item=venda_obj,
            erro=write_conflict_detail(resultado.conflito),
            user=user,
            dados=resultado.dados,
        )
    assert resultado.mensagem is not None  # noqa: S101
    return _erro_venda(
        request,
        session,
        user,
        resultado.mensagem,
        venda_obj=venda_obj,
        dados=resultado.dados,
    )


@router.post("/ui/vendas")
async def _criar_venda(
    request: Request,
    session: SessionDep,
    user: _CadastrarVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    form = await request.form()
    dados_form = dict(form)
    resultado = preparar_venda(session, form, user)
    if isinstance(resultado, VendaErro):
        return _resposta_erro_preparacao_venda(request, session, user, resultado)
    assert isinstance(resultado.data, venda.VendaCreate)  # noqa: S101
    data = resultado.data

    try:
        safe_write(
            lambda: _criar_venda_com_hooks(session, data, user.id),
            conflict_msg=write_conflict_detail("Venda"),
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            raise
        return rollback_integrity_error_response(
            session,
            lambda: conflict_form_response(
                templates,
                request,
                "_form_venda.html",
                ctx_form=_ctx_form_venda(session),
                item_key="venda",
                item=None,
                erro=write_conflict_detail("Venda"),
                user=user,
                dados=dados_form,
            ),
        )
    return _ok_venda(request, session, user, limit=limit, offset=offset)


@router.post("/ui/vendas/{item_id}")
async def _atualizar_venda(
    item_id: int,
    request: Request,
    session: SessionDep,
    user: _EditarVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    obj = found(venda.get(session, item_id), "Venda")
    form = await request.form()
    dados_form = dict(form)
    resultado = preparar_venda(session, form, user, obj=obj)
    if isinstance(resultado, VendaErro):
        return _resposta_erro_preparacao_venda(
            request, session, user, resultado, venda_obj=obj
        )
    assert isinstance(resultado.data, venda.VendaUpdate)  # noqa: S101
    data = resultado.data

    try:
        safe_write(
            lambda: venda.update(session, obj, data, user.id),
            conflict_msg=write_conflict_detail("Venda"),
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            raise
        return rollback_integrity_error_response(
            session,
            lambda: conflict_form_response(
                templates,
                request,
                "_form_venda.html",
                ctx_form=_ctx_form_venda(session),
                item_key="venda",
                item=obj,
                erro=write_conflict_detail("Venda"),
                user=user,
                dados=dados_form,
            ),
        )
    return _ok_venda(request, session, user, limit=limit, offset=offset)


def _criar_venda_com_hooks(
    session: Session, data: venda.VendaCreate, actor_id: int | None
) -> venda.Venda:
    obj = venda.create(session, data, actor_id)
    _agendar_persistencia_contrato_venda(session, obj, actor_id)
    whatsapp.notificar_venda(session, obj)
    return obj


@router.get("/ui/vendas/{item_id}/contrato")
def _baixar_contrato_venda(
    item_id: int, session: SessionDep, _: _BaixarContratoVendaDep
) -> RedirectResponse:
    obj = found(venda.get(session, item_id), "Venda")
    documentos = documento_contrato_venda.list_by_venda(session, obj.id)
    if not documentos:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    documento = max(documentos, key=lambda item: item.id)
    return RedirectResponse(documento.url)


@router.post("/ui/vendas/{item_id}/contrato/regerar")
def _regerar_contrato_venda(
    item_id: int, session: SessionDep, user: _EditarVendaDep
) -> RedirectResponse:
    """Recria o PDF do contrato com o layout e os dados atuais da venda.

    Necessário para vendas cujo contrato foi gerado antes de uma mudança no
    layout ou nos dados cadastrais da empresa — o PDF salvo não é atualizado
    sozinho quando esses dados mudam.
    """
    obj = found(venda.get(session, item_id), "Venda")
    _persistir_contrato_venda(session, obj, user.id)
    return RedirectResponse(f"/ui/vendas/{item_id}/contrato", status_code=303)


_FecharVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "fechar"))
]


@router.get("/ui/vendas/{item_id}/fechamento")
def _form_fechamento_venda(
    item_id: int, request: Request, session: SessionDep, user: _FecharVendaDep
) -> HTMLResponse:
    obj = found(venda.get(session, item_id), "Venda")
    preview = fechamento_venda.preview(session, obj)
    return templates.TemplateResponse(
        request,
        "_modal_fechamento_venda.html",
        {
            "venda": obj,
            "preview": preview,
            "fechamento": None,
            "user": user,
            "erro": None,
        },
    )


@router.post("/ui/vendas/{item_id}/fechamento")
async def _confirmar_fechamento_venda(
    item_id: int,
    request: Request,
    session: SessionDep,
    user: _FecharVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    obj = found(venda.get(session, item_id), "Venda")
    form = await request.form()
    investidores = form.getlist("investidor_id")
    percentuais = form.getlist("percentual")
    participacoes = [
        {
            "investidor_id": investidor_id,
            "percentual": str(percentual).strip().replace(",", "."),
        }
        for investidor_id, percentual in zip(investidores, percentuais, strict=False)
        if str(percentual).strip()
    ]
    try:
        data = fechamento_venda.FechamentoVendaCreate.model_validate(
            {"participacoes": participacoes}
        )
        fechamento_venda.confirmar(session, obj, data, usuario_id=user.id)
    except (ValidationError, fechamento_venda.FechamentoVendaError) as exc:
        msg = (
            validation_error_detail(exc)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        response = templates.TemplateResponse(
            request,
            "_modal_fechamento_venda.html",
            {
                "venda": obj,
                "preview": fechamento_venda.preview(session, obj),
                "fechamento": None,
                "user": user,
                "erro": msg,
            },
            status_code=400,
        )
        response.headers["HX-Retarget"] = "#modal"
        response.headers["HX-Reswap"] = "innerHTML"
        return response
    vendas = venda.list_all(session, limit=limit, offset=offset)
    return templates.TemplateResponse(
        request,
        "_vendas_ok.html",
        {"user": user, "vendas": vendas, **_ctx_lista_vendas(session, vendas)},
    )


@router.get("/ui/fechamentos-vendas/{fechamento_id}")
def _detalhe_fechamento_venda(
    fechamento_id: int,
    request: Request,
    session: SessionDep,
    user: _VerFechamentoVendaDep,
) -> HTMLResponse:
    fechamento = found(fechamento_venda.get(session, fechamento_id), "Fechamento")
    return templates.TemplateResponse(
        request,
        "_modal_fechamento_venda.html",
        {
            "venda": fechamento.venda,
            "preview": None,
            "fechamento": fechamento,
            "user": user,
            "erro": None,
        },
    )
