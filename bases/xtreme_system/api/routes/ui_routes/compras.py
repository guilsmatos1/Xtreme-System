"""HTMX routes for compras."""

from datetime import UTC, datetime
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
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
    CrudUIResourceConfig,
    CrudUIRouteConfig,
    CrudUITemplateConfig,
    register_crud_ui_routes,
)
from xtreme_system.api.crud_writes import delete_with_hook
from xtreme_system.api.deps import (
    SessionDep,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.attachment_routes import (
    AttachmentRouteConfig,
    callback_from,
    register_attachment_routes,
)
from xtreme_system.api.routes.ui_routes.client_resolution import resolver_cliente
from xtreme_system.api.routes.ui_routes.nested_writes import (
    criar_aninhado_ou_resposta_conflito,
    rollback_se_criou_aninhados,
)
from xtreme_system.api.routes.ui_routes.upload_files import (
    remover_upload,
    uploaded_file_path,
)
from xtreme_system.api.routes.ui_routes.upload_paths import (
    uploads_compra_dir,
)
from xtreme_system.api.routes.ui_routes.upload_validation import validar_uploads
from xtreme_system.api.routes.ui_routes.uploads import salvar_arquivos
from xtreme_system.api.routes.ui_routes.vehicle_resolution import (
    resolver_veiculo_inline,
)
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.imagem_comprovante_compra import core as imagem_comprovante_compra
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.workflow.core import (
    sincronizar_caixa_compra,
    validate_cliente_veiculo_fks,
)

router = APIRouter()

_EditarCompraDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "editar"))
]
_CadastrarCompraDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "cadastrar"))
]
_ExcluirComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "excluir_comprovante"))
]
_AbrirComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "abrir_comprovante"))
]
_EnviarComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "enviar_comprovante"))
]


def _investidor_padrao_id(investidores: list[investidor.Investidor]) -> int | None:
    for inv in investidores:
        if inv.nome.strip().lower() == "xtreme":
            return inv.id
    return None


def _ctx_form_compra(session: Session) -> dict[str, Any]:
    investidores = investidor.list_all(session)
    return {
        "clientes": cliente.list_all(session),
        "data_atual": datetime.now(UTC).date().isoformat(),
        "tipos_cliente": list(cliente.TipoCliente),
        "tipos": list(veiculo.TipoVeiculo),
        "tipo_entradas": list(veiculo.TipoEntrada),
        "investidores": investidores,
        "investidor_padrao_id": _investidor_padrao_id(investidores),
        "idempotency_key": uuid4().hex,
    }


def _parse_compra_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("debitos") == "":
        data["debitos"] = None
    elif isinstance(data.get("debitos"), str):
        data["debitos"] = data["debitos"].replace(",", ".")
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if not data.get("data_compra"):
        data["data_compra"] = str(datetime.now(UTC).date())
    return data


def _ctx_lista_compras(
    session: Session, compras: list[compra.Compra]
) -> dict[str, Any]:
    compra_ids = [item.id for item in compras]
    comprovantes_por_compra: dict[
        int, list[imagem_comprovante_compra.ImagemComprovanteCompra]
    ] = {compra_id: [] for compra_id in compra_ids}
    for comprovante in imagem_comprovante_compra.list_by_compra_ids(
        session, compra_ids
    ):
        comprovantes_por_compra[comprovante.compra_id].append(comprovante)
    return {
        "comprovantes_por_compra": comprovantes_por_compra,
    }


def _remover_arquivos_comprovantes(
    session: Session, obj: compra.Compra, _actor_id: int | None = None
) -> None:
    for comprovante in imagem_comprovante_compra.list_by_compra(session, obj.id):
        path = uploaded_file_path(comprovante.url or "")
        if path is not None:
            remover_upload(path)


def _preparar_exclusao_compra(
    session: Session, obj: compra.Compra, actor_id: int | None = None
) -> None:
    _remover_arquivos_comprovantes(session, obj, actor_id)


def _deletar_veiculo_apos_compra(
    session: Session, obj: compra.Compra, actor_id: int | None = None
) -> None:
    veiculo_obj = veiculo.get(session, obj.veiculo_id)
    if veiculo_obj:
        delete_with_hook(
            veiculo,
            session,
            veiculo_obj,
            caixa.deletar_lancamento_veiculo,
            actor_id,
        )


def _comprovantes_context(
    session: Session, compra_obj: compra.Compra, _user: usuario.Usuario
) -> dict[str, Any]:
    return {
        "comprovantes": imagem_comprovante_compra.list_by_compra(session, compra_obj.id)
    }


register_attachment_routes(
    router,
    AttachmentRouteConfig(
        name="compra_comprovantes",
        path="/ui/compras/{compra_id}/comprovantes",
        parent_param="compra_id",
        attachment_param="comprovante_id",
        parent_loader=callback_from(globals(), "compra.get"),
        attachment_loader=callback_from(globals(), "imagem_comprovante_compra.get"),
        parent_label="Compra",
        parent_context_key="compra",
        template="_modal_comprovantes_compra.html",
        upload_dir=callback_from(globals(), "uploads_compra_dir"),
        url_prefix=lambda item_id: f"/static/uploads/compras/{item_id}/comprovantes",
        create_fn=callback_from(globals(), "imagem_comprovante_compra.create"),
        schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
        fk_field="compra_id",
        delete_fn=callback_from(globals(), "imagem_comprovante_compra.delete"),
        upload_field="comprovantes",
        attachment_label="Comprovante",
        get_dependency=_AbrirComprovanteDep,
        upload_dependency=_EnviarComprovanteDep,
        delete_dependency=_ExcluirComprovanteDep,
        refresh_parent=False,
        extra_context=_comprovantes_context,
    ),
)


def _resolver_veiculo(
    session: Session, form: Any
) -> tuple[veiculo.Veiculo | None, veiculo.VeiculoCreate | None, str | None]:
    veiculo_sel = str(form.get("veiculo_id") or "").strip()
    if veiculo_sel:
        try:
            existente = veiculo.get(session, int(veiculo_sel))
        except ValueError:
            existente = None
        if existente is None:
            return None, None, "Veículo inválido ou inexistente"
        return existente, None, None

    return resolver_veiculo_inline(
        session,
        form,
        prefix="vei_",
        tipo_entrada=form.get("vei_tipo_entrada"),
        preco=None,
        required=True,
        error_label="do veículo",
    )


def _sincronizar_status_veiculo_compra(
    session: Session, obj: compra.Compra, actor_id: int | None = None
) -> None:
    veiculo_obj = session.get(veiculo.Veiculo, obj.veiculo_id, with_for_update=True)
    if veiculo_obj is None:
        return
    if obj.status == compra.StatusCompra.cancelado:
        veiculo_obj.status = veiculo.StatusVeiculo.cancelado
    elif veiculo_obj.status == veiculo.StatusVeiculo.cancelado:
        veiculo_obj.status = veiculo.StatusVeiculo.disponivel
    session.flush()
    sincronizar_caixa_compra(session, obj, actor_id)


def _erro_compra(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    msg: str,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return error_response(
        templates,
        request,
        "_form_compra.html",
        ctx_form=_ctx_form_compra(session),
        item_key="compra",
        item=None,
        erro=msg,
        status_code=400,
        user=user,
        dados=dados,
    )


def _ok_compra(
    request: Request,
    session: Session,
    user: Any,
    *,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    compras = compra.list_all(session, limit=limit, offset=offset)
    return ok_response(
        templates,
        request,
        "_compras_ok.html",
        user=user,
        list_key="compras",
        lista=compras,
        ctx_list={},
    )


@router.post("/ui/compras")
async def _criar_compra(  # noqa: PLR0911
    request: Request,
    session: SessionDep,
    user: _CadastrarCompraDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    form = await request.form()
    dados_form = dict(form)
    idempotency_key = str(form.get("idempotency_key") or "").strip() or None
    if idempotency_key and compra.get_by_idempotency_key(session, idempotency_key):
        return _ok_compra(request, session, user, limit=limit, offset=offset)

    comprovantes = cast(
        list[UploadFile],
        [
            arquivo
            for arquivo in form.getlist("comprovantes_pagamento")
            if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
        ],
    )
    if not perfil.pode_operacao(user, "compras", "enviar_comprovante"):
        comprovantes = []
    erro = validar_uploads(comprovantes)
    if erro:
        return _erro_compra(request, session, user, erro, dados_form)

    cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
    if erro:
        return _erro_compra(request, session, user, erro, dados_form)

    veiculo_obj, novo_veiculo_data, erro = _resolver_veiculo(session, form)
    if erro:
        return _erro_compra(request, session, user, erro, dados_form)

    novo_cliente_obj, conflito = criar_aninhado_ou_resposta_conflito(
        session,
        novo_cliente_data,
        cliente.create,
        user.id,
    )
    if conflito:
        return conflict_form_response(
            templates,
            request,
            "_form_compra.html",
            ctx_form=_ctx_form_compra(session),
            item_key="compra",
            item=None,
            erro=write_conflict_detail("Cliente"),
            user=user,
            dados=dados_form,
        )
    if novo_cliente_obj is not None:
        cliente_obj = novo_cliente_obj

    novo_veiculo_obj, conflito = criar_aninhado_ou_resposta_conflito(
        session,
        novo_veiculo_data,
        veiculo.create,
        user.id,
    )
    if conflito:
        return conflict_form_response(
            templates,
            request,
            "_form_compra.html",
            ctx_form=_ctx_form_compra(session),
            item_key="compra",
            item=None,
            erro=write_conflict_detail("Veículo"),
            user=user,
            dados=dados_form,
        )
    if novo_veiculo_obj is not None:
        veiculo_obj = novo_veiculo_obj

    assert cliente_obj is not None  # noqa: S101
    assert veiculo_obj is not None  # noqa: S101

    try:
        data = compra.CompraCreate.model_validate(
            perfil.campos_form_visiveis(
                user,
                "compras",
                {
                    **_parse_compra_form(form),
                    "cliente_id": cliente_obj.id,
                    "veiculo_id": veiculo_obj.id,
                    "usuario_id": user.id,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        validate_cliente_veiculo_fks(session, data)
    except (ValidationError, HTTPException) as exc:
        rollback_se_criou_aninhados(session, novo_cliente_data, novo_veiculo_data)
        msg = (
            str(exc.detail)
            if isinstance(exc, HTTPException)
            else validation_error_detail(exc)
        )
        return _erro_compra(request, session, user, msg, dados_form)

    try:
        obj = compra.create(session, data, user.id)
        sincronizar_caixa_compra(session, obj, user.id)
        salvar_arquivos(
            session,
            upload_dir=uploads_compra_dir(obj.id),
            url_prefix=f"/static/uploads/compras/{obj.id}/comprovantes",
            create_fn=imagem_comprovante_compra.create,
            schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
            fk_field="compra_id",
            fk_id=obj.id,
            arquivos=comprovantes,
            actor_id=user.id,
        )
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: (
                _ok_compra(request, session, user, limit=limit, offset=offset)
                if idempotency_key
                and compra.get_by_idempotency_key(session, idempotency_key)
                else conflict_form_response(
                    templates,
                    request,
                    "_form_compra.html",
                    ctx_form=_ctx_form_compra(session),
                    item_key="compra",
                    item=None,
                    erro=write_conflict_detail("Compra"),
                    user=user,
                    dados=dados_form,
                )
            ),
        )
    return _ok_compra(request, session, user, limit=limit, offset=offset)


register_crud_ui_routes(
    router,
    templates,
    compra,
    "/ui/compras",
    resource=CrudUIResourceConfig(
        label="Compra",
        create_schema=compra.CompraCreate,
        update_schema=compra.CompraUpdate,
        list_key="compras",
        item_key="compra",
    ),
    templates_config=CrudUITemplateConfig(
        list_template="compras.html",
        list_partial_template="_linhas_compras.html",
        ok_partial_template="_compras_ok.html",
        form_template="_form_compra.html",
    ),
    behavior=CrudUIBehaviorConfig(
        ctx_form=_ctx_form_compra,
        ctx_list=_ctx_lista_compras,
        parse_form=_parse_compra_form,
        before_create=validate_cliente_veiculo_fks,
        before_update=validate_cliente_veiculo_fks,
        after_update=_sincronizar_status_veiculo_compra,
        before_delete=_preparar_exclusao_compra,
        after_delete=_deletar_veiculo_apos_compra,
    ),
    listing=ListingSpec(
        searchable=True,
        source="query",
        query_func=compra.query,
        search_query_func=compra.search_query,
        sort_fields={
            "criado_em": SortField("criado_em", compra.Compra.criado_em),
            "cliente": SortField(
                lambda c: _sort_key(c.cliente.nome), cliente.Cliente.nome
            ),
            "documento": SortField(
                lambda c: _sort_key(c.cliente.documento or ""),
                cliente.Cliente.documento,
            ),
            "modelo": SortField(
                lambda c: _sort_key(c.veiculo.modelo), veiculo.Veiculo.modelo
            ),
            "placa": SortField(
                lambda c: _sort_key(c.veiculo.placa), veiculo.Veiculo.placa
            ),
            "data": SortField("criado_em", compra.Compra.criado_em),
            "valor": SortField("valor_compra", compra.Compra.valor_compra),
            "status": SortField("status", compra.Compra.status),
            "observacoes": SortField(
                lambda c: _sort_key(c.observacoes or ""), compra.Compra.observacoes
            ),
            "usuario": SortField(
                lambda c: _sort_key(
                    (c.usuario.nome or c.usuario.username) if c.usuario else ""
                ),
                usuario.Usuario.nome,
            ),
        },
        default_sort="criado_em",
        default_order="desc",
    ),
    export=CrudUIExportConfig(
        csv_filename="compras.csv",
        columns=[
            ColumnSpec("id", "ID", table=False, export=lambda c: c.id),
            ColumnSpec(
                "criado_em",
                "Data/Hora",
                field="criado_em",
                export=lambda c: c.criado_em.isoformat(),
            ),
            ColumnSpec(
                "cliente",
                "Nome do Cliente",
                field="cliente",
                export=lambda c: c.cliente.nome,
            ),
            ColumnSpec(
                "documento_cliente",
                "Documento do Cliente",
                field="documento_cliente",
                export=lambda c: c.cliente.documento or "",
            ),
            ColumnSpec(
                "status", "Estado", field="status", export=lambda c: c.status.value
            ),
            ColumnSpec(
                "placa", "Placa", field="placa", export=lambda c: c.veiculo.placa
            ),
            ColumnSpec(
                "veiculo", "Veiculo", field="veiculo", export=lambda c: c.veiculo.modelo
            ),
            ColumnSpec(
                "valor_compra",
                "Valor Compra",
                field="valor_compra",
                export=lambda c: f"{c.valor_compra:.2f}",
            ),
            ColumnSpec(
                "observacoes",
                "Observacoes",
                field="observacoes",
                export=lambda c: c.observacoes or "",
            ),
            ColumnSpec(
                "usuario",
                "Usuario",
                field="usuario",
                export=lambda c: (
                    (c.usuario.nome or c.usuario.username) if c.usuario else ""
                ),
            ),
        ],
        pagina="compras",
    ),
    routes=CrudUIRouteConfig(
        register_create=False,
        cadastrar_dep=require_operacao("compras", "cadastrar"),
        editar_dep=require_operacao("compras", "editar"),
        excluir_dep=require_operacao("compras", "excluir"),
    ),
)
