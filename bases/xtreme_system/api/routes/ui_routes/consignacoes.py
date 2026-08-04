"""HTMX routes for consignacoes."""

from datetime import UTC, datetime
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, UploadFile
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
    uploads_consignacao_dir,
)
from xtreme_system.api.routes.ui_routes.upload_validation import validar_uploads
from xtreme_system.api.routes.ui_routes.uploads import salvar_arquivos
from xtreme_system.api.routes.ui_routes.vehicle_resolution import (
    resolver_veiculo_inline,
)
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.consignacao import core as consignacao
from xtreme_system.imagem_contrato_consignacao import (
    core as imagem_contrato_consignacao,
)
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.workflow.core import (
    validate_cliente_veiculo_fks,
)

_EditarConsignacaoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("consignacoes", "editar"))
]
_CadastrarConsignacaoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("consignacoes", "cadastrar"))
]
_ExcluirContratoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("consignacoes", "excluir_contrato"))
]
_AbrirContratoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("consignacoes", "abrir_contrato"))
]
_EnviarContratoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("consignacoes", "enviar_contrato"))
]


def _investidor_padrao_id(investidores: list[investidor.Investidor]) -> int | None:
    for inv in investidores:
        if inv.nome.strip().lower() == "xtreme":
            return inv.id
    return None


def _ctx_form_consignacao(session: Session) -> dict[str, Any]:
    investidores = investidor.list_all(session)
    return {
        "clientes": cliente.list_all(session),
        "data_atual": datetime.now(UTC).date().isoformat(),
        "tipos_cliente": list(cliente.TipoCliente),
        "tipos": list(veiculo.TipoVeiculo),
        "investidores": investidores,
        "investidor_padrao_id": _investidor_padrao_id(investidores),
        "idempotency_key": uuid4().hex,
    }


def _parse_consignacao_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if isinstance(data.get("valor_venda"), str):
        data["valor_venda"] = data["valor_venda"].replace(",", ".")
    if data.get("comissao_percentual") == "":
        data["comissao_percentual"] = None
    elif isinstance(data.get("comissao_percentual"), str):
        data["comissao_percentual"] = data["comissao_percentual"].replace(",", ".")
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if not data.get("data_consignacao"):
        data["data_consignacao"] = str(datetime.now(UTC).date())
    if data.get("data_vencimento") == "":
        data["data_vencimento"] = None
    return data


def _ctx_lista_consignacoes(
    session: Session, consignacoes: list[consignacao.Consignacao]
) -> dict[str, Any]:
    consignacao_ids = [item.id for item in consignacoes]
    contratos_por_consignacao: dict[
        int, list[imagem_contrato_consignacao.ImagemContratoConsignacao]
    ] = {consignacao_id: [] for consignacao_id in consignacao_ids}
    for contrato in imagem_contrato_consignacao.list_by_consignacao_ids(
        session, consignacao_ids
    ):
        contratos_por_consignacao[contrato.consignacao_id].append(contrato)
    return {
        "contratos_por_consignacao": contratos_por_consignacao,
    }


def _remover_arquivos_contratos(
    session: Session, obj: consignacao.Consignacao, _actor_id: int | None = None
) -> None:
    for contrato in imagem_contrato_consignacao.list_by_consignacao(session, obj.id):
        path = uploaded_file_path(contrato.url or "")
        if path is not None:
            remover_upload(path)


def _preparar_exclusao_consignacao(
    session: Session, obj: consignacao.Consignacao, actor_id: int | None = None
) -> None:
    _remover_arquivos_contratos(session, obj, actor_id)


def _deletar_veiculo_apos_consignacao(
    session: Session, obj: consignacao.Consignacao, actor_id: int | None = None
) -> None:
    veiculo_obj = veiculo.get(session, obj.veiculo_id)
    if veiculo_obj:
        delete_with_hook(
            veiculo,
            session,
            veiculo_obj,
            lambda _s, _v, _a: None,
            actor_id,
        )


def _contratos_context(
    session: Session, consignacao_obj: consignacao.Consignacao, _user: usuario.Usuario
) -> dict[str, Any]:
    return {
        "contratos": imagem_contrato_consignacao.list_by_consignacao(
            session, consignacao_obj.id
        )
    }


register_attachment_routes(
    app,
    AttachmentRouteConfig(
        name="consignacao_contratos",
        path="/ui/consignacoes/{consignacao_id}/contratos",
        parent_param="consignacao_id",
        attachment_param="contrato_id",
        parent_loader=callback_from(globals(), "consignacao.get"),
        attachment_loader=callback_from(globals(), "imagem_contrato_consignacao.get"),
        parent_label="Consignação",
        parent_context_key="consignacao",
        template="_modal_contratos_consignacao.html",
        upload_dir=callback_from(globals(), "uploads_consignacao_dir"),
        url_prefix=lambda item_id: f"/static/uploads/consignacoes/{item_id}/contratos",
        create_fn=callback_from(globals(), "imagem_contrato_consignacao.create"),
        schema=imagem_contrato_consignacao.ImagemContratoConsignacaoCreate,
        fk_field="consignacao_id",
        delete_fn=callback_from(globals(), "imagem_contrato_consignacao.delete"),
        upload_field="contratos",
        attachment_label="Contrato",
        get_dependency=_AbrirContratoDep,
        upload_dependency=_EnviarContratoDep,
        delete_dependency=_ExcluirContratoDep,
        refresh_parent=False,
        extra_context=_contratos_context,
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
        tipo_entrada="consignacao",
        preco=form.get("valor_venda"),
        required=True,
        error_label="do veículo",
    )


def _sincronizar_status_veiculo_consignacao(
    session: Session, obj: consignacao.Consignacao, _actor_id: int | None = None
) -> None:
    veiculo_obj = session.get(veiculo.Veiculo, obj.veiculo_id, with_for_update=True)
    if veiculo_obj is None:
        return
    if obj.status == consignacao.StatusConsignacao.cancelada:
        veiculo_obj.status = veiculo.StatusVeiculo.cancelado
    elif veiculo_obj.status == veiculo.StatusVeiculo.cancelado:
        veiculo_obj.status = veiculo.StatusVeiculo.disponivel
    session.flush()


def _erro_consignacao(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    msg: str,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return error_response(
        templates,
        request,
        "_form_consignacao.html",
        ctx_form=_ctx_form_consignacao(session),
        item_key="consignacao",
        item=None,
        erro=msg,
        status_code=400,
        user=user,
        dados=dados,
    )


def _ok_consignacao(
    request: Request,
    session: Session,
    user: Any,
    *,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    consignacoes = consignacao.list_all(session, limit=limit, offset=offset)
    return ok_response(
        templates,
        request,
        "_consignacoes_ok.html",
        user=user,
        list_key="consignacoes",
        lista=consignacoes,
        ctx_list={},
    )


@app.post("/ui/consignacoes")
async def _criar_consignacao(  # noqa: PLR0911
    request: Request,
    session: SessionDep,
    user: _CadastrarConsignacaoDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    form = await request.form()
    dados_form = dict(form)
    idempotency_key = str(form.get("idempotency_key") or "").strip() or None
    if idempotency_key and consignacao.get_by_idempotency_key(session, idempotency_key):
        return _ok_consignacao(request, session, user, limit=limit, offset=offset)

    contratos = cast(
        list[UploadFile],
        [
            arquivo
            for arquivo in form.getlist("contratos_consignacao")
            if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
        ],
    )
    if not perfil.pode_operacao(user, "consignacoes", "enviar_contrato"):
        contratos = []
    erro = validar_uploads(contratos)
    if erro:
        return _erro_consignacao(request, session, user, erro, dados_form)

    cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
    if erro:
        return _erro_consignacao(request, session, user, erro, dados_form)

    veiculo_obj, novo_veiculo_data, erro = _resolver_veiculo(session, form)
    if erro:
        return _erro_consignacao(request, session, user, erro, dados_form)

    novo_cliente_obj, response = criar_aninhado_ou_resposta_conflito(
        session,
        novo_cliente_data,
        cliente.create,
        user.id,
        lambda: conflict_form_response(
            templates,
            request,
            "_form_consignacao.html",
            ctx_form=_ctx_form_consignacao(session),
            item_key="consignacao",
            item=None,
            erro=write_conflict_detail("Cliente"),
            user=user,
            dados=dados_form,
        ),
    )
    if response is not None:
        return response
    if novo_cliente_obj is not None:
        cliente_obj = novo_cliente_obj

    novo_veiculo_obj, response = criar_aninhado_ou_resposta_conflito(
        session,
        novo_veiculo_data,
        veiculo.create,
        user.id,
        lambda: conflict_form_response(
            templates,
            request,
            "_form_consignacao.html",
            ctx_form=_ctx_form_consignacao(session),
            item_key="consignacao",
            item=None,
            erro=write_conflict_detail("Veículo"),
            user=user,
            dados=dados_form,
        ),
    )
    if response is not None:
        return response
    if novo_veiculo_obj is not None:
        veiculo_obj = novo_veiculo_obj

    assert cliente_obj is not None  # noqa: S101
    assert veiculo_obj is not None  # noqa: S101

    try:
        data = consignacao.ConsignacaoCreate.model_validate(
            perfil.campos_form_visiveis(
                user,
                "consignacoes",
                {
                    **_parse_consignacao_form(form),
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
        return _erro_consignacao(request, session, user, msg, dados_form)

    try:
        obj = consignacao.create(session, data, user.id)
        salvar_arquivos(
            session,
            upload_dir=uploads_consignacao_dir(obj.id),
            url_prefix=f"/static/uploads/consignacoes/{obj.id}/contratos",
            create_fn=imagem_contrato_consignacao.create,
            schema=imagem_contrato_consignacao.ImagemContratoConsignacaoCreate,
            fk_field="consignacao_id",
            fk_id=obj.id,
            arquivos=contratos,
            actor_id=user.id,
        )
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: (
                _ok_consignacao(request, session, user, limit=limit, offset=offset)
                if idempotency_key
                and consignacao.get_by_idempotency_key(session, idempotency_key)
                else conflict_form_response(
                    templates,
                    request,
                    "_form_consignacao.html",
                    ctx_form=_ctx_form_consignacao(session),
                    item_key="consignacao",
                    item=None,
                    erro=write_conflict_detail("Consignação"),
                    user=user,
                    dados=dados_form,
                )
            ),
        )
    return _ok_consignacao(request, session, user, limit=limit, offset=offset)


register_crud_ui_routes(
    app,
    templates,
    consignacao,
    "/ui/consignacoes",
    resource=CrudUIResourceConfig(
        label="Consignação",
        create_schema=consignacao.ConsignacaoCreate,
        update_schema=consignacao.ConsignacaoUpdate,
        list_key="consignacoes",
        item_key="consignacao",
    ),
    templates_config=CrudUITemplateConfig(
        list_template="consignacoes.html",
        list_partial_template="_linhas_consignacoes.html",
        ok_partial_template="_consignacoes_ok.html",
        form_template="_form_consignacao.html",
    ),
    behavior=CrudUIBehaviorConfig(
        ctx_form=_ctx_form_consignacao,
        ctx_list=_ctx_lista_consignacoes,
        parse_form=_parse_consignacao_form,
        before_create=validate_cliente_veiculo_fks,
        before_update=validate_cliente_veiculo_fks,
        after_update=_sincronizar_status_veiculo_consignacao,
        before_delete=_preparar_exclusao_consignacao,
        after_delete=_deletar_veiculo_apos_consignacao,
    ),
    listing=ListingSpec(
        searchable=True,
        source="query",
        query_func=consignacao.query,
        search_query_func=consignacao.search_query,
        sort_fields={
            "criado_em": SortField("criado_em", consignacao.Consignacao.criado_em),
            "proprietario": SortField(
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
            "data": SortField("criado_em", consignacao.Consignacao.criado_em),
            "valor": SortField("valor_venda", consignacao.Consignacao.valor_venda),
            "comissao": SortField(
                "comissao_percentual", consignacao.Consignacao.comissao_percentual
            ),
            "vencimento": SortField(
                "data_vencimento", consignacao.Consignacao.data_vencimento
            ),
            "status": SortField("status", consignacao.Consignacao.status),
            "observacoes": SortField(
                lambda c: _sort_key(c.observacoes or ""),
                consignacao.Consignacao.observacoes,
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
        csv_filename="consignacoes.csv",
        columns=[
            ColumnSpec("id", "ID", table=False, export=lambda c: c.id),
            ColumnSpec(
                "criado_em",
                "Data/Hora",
                field="criado_em",
                export=lambda c: c.criado_em.isoformat(),
            ),
            ColumnSpec(
                "proprietario",
                "Proprietário",
                field="proprietario",
                export=lambda c: c.cliente.nome,
            ),
            ColumnSpec(
                "documento",
                "Documento do Proprietário",
                field="documento",
                export=lambda c: c.cliente.documento or "",
            ),
            ColumnSpec(
                "status", "Estado", field="status", export=lambda c: c.status.value
            ),
            ColumnSpec(
                "placa", "Placa", field="placa", export=lambda c: c.veiculo.placa
            ),
            ColumnSpec(
                "modelo", "Veículo", field="modelo", export=lambda c: c.veiculo.modelo
            ),
            ColumnSpec(
                "valor_venda",
                "Valor de Venda",
                field="valor_venda",
                export=lambda c: f"{c.valor_venda:.2f}" if c.valor_venda else "",
            ),
            ColumnSpec(
                "comissao_percentual",
                "Comissão (%)",
                field="comissao_percentual",
                export=lambda c: (
                    f"{c.comissao_percentual:.2f}" if c.comissao_percentual else ""
                ),
            ),
            ColumnSpec(
                "data_vencimento",
                "Vencimento",
                field="data_vencimento",
                export=lambda c: (
                    c.data_vencimento.isoformat() if c.data_vencimento else ""
                ),
            ),
            ColumnSpec(
                "observacoes",
                "Observações",
                field="observacoes",
                export=lambda c: c.observacoes or "",
            ),
            ColumnSpec(
                "usuario",
                "Usuário",
                field="usuario",
                export=lambda c: (
                    (c.usuario.nome or c.usuario.username) if c.usuario else ""
                ),
            ),
        ],
        pagina="consignacoes",
    ),
    routes=CrudUIRouteConfig(
        register_create=False,
        cadastrar_dep=require_operacao("consignacoes", "cadastrar"),
        editar_dep=require_operacao("consignacoes", "editar"),
        excluir_dep=require_operacao("consignacoes", "excluir"),
    ),
)
