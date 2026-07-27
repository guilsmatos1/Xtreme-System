"""HTMX routes for vendas."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import (
    error_response,
    ok_response,
    rollback_integrity_error_response,
)
from xtreme_system.api.crud_ui.routes import register_crud_ui_routes
from xtreme_system.api.crud_writes import safe_write
from xtreme_system.api.deps import (
    SessionDep,
    _found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.common import (
    _uploaded_file_path,
    _uploads_contrato_venda_dir,
    criar_aninhado_ou_resposta_conflito,
    resolver_cliente,
    rollback_se_criou_aninhados,
)
from xtreme_system.api.routes.workflows import (
    recompute_vehicle_status_on_delete,
    validate_cliente_veiculo_fks,
    validate_valores_venda_update,
    validate_veiculo_disponivel_para_venda,
)
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.database.core import register_post_rollback
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
from xtreme_system.empresa import core as empresa
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)

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
    veiculos = veiculo.list_all(session)
    veiculos_disponiveis = [
        v for v in veiculos if v.status == veiculo.StatusVeiculo.disponivel
    ]
    return {
        "clientes": cliente.list_all(session),
        "veiculos": veiculos_disponiveis,
        "veiculos_troca": veiculos,
        "status": list(venda.StatusVenda),
        "tipos": list(cliente.TipoCliente),
    }


def _parse_venda_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("valor_entrada") == "":
        data["valor_entrada"] = None
    if data.get("debitos") == "":
        data["debitos"] = None
    if data.get("km") == "":
        data["km"] = None
    if data.get("parcelas") == "":
        data["parcelas"] = None
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if data.get("veiculo_troca_id") == "":
        data["veiculo_troca_id"] = None
    if data.get("valor_diferenca") == "":
        data["valor_diferenca"] = None
    if data.get("valor_pendente") == "":
        data["valor_pendente"] = None
    if data.get("datas_pagamento") == "":
        data["datas_pagamento"] = None
    data["pagamento_pendente"] = bool(data.get("pagamento_pendente"))
    if not data.get("data_venda"):
        data["data_venda"] = str(datetime.now(UTC).date())
    return data


def _filtrar_campos_ocultos_venda(
    user: usuario.Usuario, data: dict[str, Any]
) -> dict[str, Any]:
    return perfil.filtrar_campos_form_ocultos(user, "vendas", data)


def _validate_venda_update(
    session: Session, obj: venda.Venda, data: venda.VendaUpdate
) -> None:
    validate_cliente_veiculo_fks(session, data)
    validate_valores_venda_update(obj, data)
    if data.veiculo_id is not None and data.veiculo_id != obj.veiculo_id:
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)


def _ctx_lista_vendas(session: Session, _vendas: list[Any]) -> dict[str, Any]:
    return {
        "fechamentos_by_venda": fechamento_venda.ids_by_venda_ids(
            session, [item.id for item in _vendas]
        )
    }


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
    ctx_list=_ctx_lista_vendas,
    searchable=True,
    search_func=venda.search,
    parse_form=_parse_venda_form,
    before_delete=recompute_vehicle_status_on_delete,
    register_create=False,
    register_update=False,
    sort_fields={
        "cliente": lambda v: _sort_key(v.cliente.nome),
        "veiculo": lambda v: _sort_key(v.veiculo.modelo),
        "data": "data_venda",
        "valor": "valor_venda",
        "entrada": "valor_entrada",
        "divida": "valor_pendente",
        "pagamento": "forma_pagamento",
        "parcelas": "parcelas",
        "status": "status",
        "vendedor": lambda v: _sort_key(
            (v.vendedor.nome or v.vendedor.username) if v.vendedor else ""
        ),
    },
    sql_sort_fields={
        "cliente": cliente.Cliente.nome,
        "veiculo": veiculo.Veiculo.modelo,
        "data": venda.Venda.data_venda,
        "valor": venda.Venda.valor_venda,
        "entrada": venda.Venda.valor_entrada,
        "divida": venda.Venda.valor_pendente,
        "pagamento": venda.Venda.forma_pagamento,
        "parcelas": venda.Venda.parcelas,
        "status": venda.Venda.status,
        "vendedor": usuario.Usuario.nome,
    },
    query_func=venda.query,
    search_query_func=venda.search_query,
    csv_filename="vendas.csv",
    csv_headers=[
        "ID",
        "Cliente",
        "Veiculo",
        "Data",
        "Valor Venda",
        "Valor Entrada",
        "Debitos",
        "KM",
        "Veiculo Troca",
        "Valor Diferenca",
        "Pagamento Pendente",
        "Valor Pendente",
        "Datas Pagamento",
        "Forma Pagamento",
        "Parcelas",
        "Status",
        "Observacoes",
        "Usuario",
    ],
    csv_fields=[
        None,
        "cliente",
        "veiculo",
        "data_venda",
        "valor_venda",
        "valor_entrada",
        "debitos",
        "km",
        "veiculo_troca",
        "valor_diferenca",
        "pagamento_pendente",
        "valor_pendente",
        "datas_pagamento",
        "forma_pagamento",
        "parcelas",
        "status",
        "observacoes",
        "vendedor",
    ],
    csv_row=lambda v: [
        v.id,
        v.cliente.nome,
        f"{v.veiculo.modelo} ({v.veiculo.placa})",
        v.data_venda.isoformat() if v.data_venda is not None else "",
        f"{v.valor_venda:.2f}",
        f"{v.valor_entrada:.2f}" if v.valor_entrada is not None else "",
        f"{v.debitos:.2f}" if v.debitos is not None else "",
        v.km if v.km is not None else "",
        (
            f"{v.veiculo_troca.modelo} ({v.veiculo_troca.placa})"
            if v.veiculo_troca is not None
            else ""
        ),
        f"{v.valor_diferenca:.2f}" if v.valor_diferenca is not None else "",
        "Sim" if v.pagamento_pendente else "Não",
        f"{v.valor_pendente:.2f}" if v.valor_pendente is not None else "",
        v.datas_pagamento or "",
        v.forma_pagamento,
        v.parcelas,
        v.status.value,
        v.observacoes or "",
        (v.vendedor.nome or v.vendedor.username) if v.vendedor else "",
    ],
    cadastrar_dep=require_operacao("vendas", "cadastrar"),
    editar_dep=require_operacao("vendas", "editar"),
    excluir_dep=require_operacao("vendas", "excluir"),
    pagina="vendas",
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
    )


def _persistir_contrato_venda(
    session: Session, obj: venda.Venda, actor_id: int | None = None
) -> None:
    upload_dir = _uploads_contrato_venda_dir(obj.id)
    filename = f"{uuid4().hex}.pdf"
    path = upload_dir / filename
    tmp_path = upload_dir / f".{filename}.tmp"
    config_empresa = empresa.get_config(session)
    logo_path = (
        _uploaded_file_path(config_empresa.logo_url)
        if config_empresa.logo_url
        else None
    )
    if logo_path is not None and not logo_path.exists():
        logo_path = None
    pdf = documento_contrato_venda.gerar_pdf(obj, config_empresa, logo_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.write_bytes(pdf)
        with tmp_path.open("rb") as arquivo:
            os.fsync(arquivo.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    def _cleanup_contract_on_rollback(
        *, path: Path = path, tmp_path: Path = tmp_path
    ) -> None:
        path.unlink(missing_ok=True)
        tmp_path.unlink(missing_ok=True)

    register_post_rollback(session, _cleanup_contract_on_rollback)
    documento_contrato_venda.create(
        session,
        documento_contrato_venda.DocumentoContratoVendaCreate(
            venda_id=obj.id,
            url=f"/static/uploads/vendas/{obj.id}/contrato/{filename}",
        ),
        actor_id,
    )


@app.post("/ui/vendas")
async def _criar_venda(
    request: Request,
    session: SessionDep,
    user: _CadastrarVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    form = await request.form()

    cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
    if erro:
        return _erro_venda(request, session, user, erro)

    novo_cliente_obj, response = criar_aninhado_ou_resposta_conflito(
        session,
        novo_cliente_data,
        cliente.create,
        user.id,
        lambda: _erro_venda(request, session, user, "Cliente já existe"),
    )
    if response is not None:
        return response
    if novo_cliente_obj is not None:
        cliente_obj = novo_cliente_obj
    assert cliente_obj is not None  # noqa: S101 -- invariante interna: erro is None garante cliente_obj definido

    try:
        data = venda.VendaCreate.model_validate(
            _filtrar_campos_ocultos_venda(
                user,
                {
                    **_parse_venda_form(form),
                    "cliente_id": cliente_obj.id,
                    "vendedor_id": user.id,
                },
            )
        )
        validate_cliente_veiculo_fks(session, data)
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)
    except (ValidationError, HTTPException) as exc:
        rollback_se_criou_aninhados(session, novo_cliente_data)
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_venda(request, session, user, msg)

    try:
        safe_write(
            lambda: _criar_venda_com_hooks(session, data, user.id),
            conflict_msg="Venda já existe",
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            raise
        return rollback_integrity_error_response(
            session, lambda: _erro_venda(request, session, user, "Venda já existe")
        )
    return _ok_venda(request, session, user, limit=limit, offset=offset)


@app.post("/ui/vendas/{item_id}")
async def _atualizar_venda(
    item_id: int,
    request: Request,
    session: SessionDep,
    user: _EditarVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    obj = _found(venda.get(session, item_id), "Venda")
    form = await request.form()

    try:
        data = venda.VendaUpdate.model_validate(
            _filtrar_campos_ocultos_venda(user, _parse_venda_form(form))
        )
        _validate_venda_update(session, obj, data)
    except (ValidationError, HTTPException) as exc:
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_venda(request, session, user, msg, venda_obj=obj)

    try:
        safe_write(
            lambda: venda.update(session, obj, data, user.id),
            conflict_msg="Venda já existe",
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            raise
        return rollback_integrity_error_response(
            session,
            lambda: _erro_venda(
                request, session, user, "Venda já existe", venda_obj=obj
            ),
        )
    return _ok_venda(request, session, user, limit=limit, offset=offset)


def _criar_venda_com_hooks(
    session: Session, data: venda.VendaCreate, actor_id: int | None
) -> venda.Venda:
    obj = venda.create(session, data, actor_id)
    _persistir_contrato_venda(session, obj, actor_id)
    whatsapp.notificar_venda(session, obj)
    return obj


@app.get("/ui/vendas/{item_id}/contrato")
def _baixar_contrato_venda(
    item_id: int, session: SessionDep, _: _BaixarContratoVendaDep
) -> RedirectResponse:
    obj = _found(venda.get(session, item_id), "Venda")
    documentos = documento_contrato_venda.list_by_venda(session, obj.id)
    if not documentos:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    documento = max(documentos, key=lambda item: item.id)
    return RedirectResponse(documento.url)


@app.post("/ui/vendas/{item_id}/contrato/regerar")
def _regerar_contrato_venda(
    item_id: int, session: SessionDep, user: _EditarVendaDep
) -> RedirectResponse:
    """Recria o PDF do contrato com o layout e os dados atuais da venda.

    Necessário para vendas cujo contrato foi gerado antes de uma mudança no
    layout ou nos dados cadastrais da empresa — o PDF salvo não é atualizado
    sozinho quando esses dados mudam.
    """
    obj = _found(venda.get(session, item_id), "Venda")
    _persistir_contrato_venda(session, obj, user.id)
    return RedirectResponse(f"/ui/vendas/{item_id}/contrato", status_code=303)


_FecharVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "fechar"))
]


@app.get("/ui/vendas/{item_id}/fechamento")
def _form_fechamento_venda(
    item_id: int, request: Request, session: SessionDep, user: _FecharVendaDep
) -> HTMLResponse:
    obj = _found(venda.get(session, item_id), "Venda")
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


@app.post("/ui/vendas/{item_id}/fechamento")
async def _confirmar_fechamento_venda(
    item_id: int,
    request: Request,
    session: SessionDep,
    user: _FecharVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    obj = _found(venda.get(session, item_id), "Venda")
    form = await request.form()
    investidores = form.getlist("investidor_id")
    percentuais = form.getlist("percentual")
    participacoes = [
        {"investidor_id": investidor_id, "percentual": percentual}
        for investidor_id, percentual in zip(investidores, percentuais, strict=False)
        if str(percentual).strip()
    ]
    try:
        data = fechamento_venda.FechamentoVendaCreate.model_validate(
            {"participacoes": participacoes}
        )
        fechamento_venda.confirmar(session, obj, data, usuario_id=user.id)
    except (ValidationError, fechamento_venda.FechamentoVendaError) as exc:
        msg = str(exc)
        if isinstance(exc, ValidationError):
            msg = "Dados inválidos"
        return templates.TemplateResponse(
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
    vendas = venda.list_all(session, limit=limit, offset=offset)
    return templates.TemplateResponse(
        request,
        "_vendas_ok.html",
        {"user": user, "vendas": vendas, **_ctx_lista_vendas(session, vendas)},
    )


@app.get("/ui/fechamentos-vendas/{fechamento_id}")
def _detalhe_fechamento_venda(
    fechamento_id: int,
    request: Request,
    session: SessionDep,
    user: _VerFechamentoVendaDep,
) -> HTMLResponse:
    fechamento = _found(fechamento_venda.get(session, fechamento_id), "Fechamento")
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
