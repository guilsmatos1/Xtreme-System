"""HTMX routes for vendas."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.responses import rollback_integrity_error_response
from xtreme_system.api.deps import (
    SessionDep,
    _found,
    require_operacao,
    templates,
)
from xtreme_system.api.route_factories import _sort_key, register_crud_ui_routes
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_contrato_venda_dir,
    resolver_cliente,
)
from xtreme_system.api.routes.workflows import (
    recompute_vehicle_status_on_delete,
    validate_cliente_veiculo_fks,
    validate_veiculo_disponivel_para_venda,
)
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.database.core import register_post_rollback
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
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
    campos_form_map = {
        "cliente": "cliente_id",
        "veiculo": "veiculo_id",
        "data_venda": "data_venda",
        "valor_venda": "valor_venda",
        "valor_entrada": "valor_entrada",
        "debitos": "debitos",
        "km": "km",
        "veiculo_troca": "veiculo_troca_id",
        "valor_diferenca": "valor_diferenca",
        "pagamento_pendente": "pagamento_pendente",
        "valor_pendente": "valor_pendente",
        "datas_pagamento": "datas_pagamento",
        "forma_pagamento": "forma_pagamento",
        "parcelas": "parcelas",
        "status": "status",
        "observacoes": "observacoes",
    }
    for campo, campo_form in campos_form_map.items():
        if not perfil.pode_ver_campo(user, "vendas", campo):
            data.pop(campo_form, None)
    return data


def _validate_venda_update(
    session: Session, obj: venda.Venda, data: venda.VendaUpdate
) -> None:
    validate_cliente_veiculo_fks(session, data)
    if data.veiculo_id is not None and data.veiculo_id != obj.veiculo_id:
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)


def _ctx_lista_vendas(session: Session, _vendas: list[Any]) -> dict[str, Any]:
    fechamentos = fechamento_venda.list_all(session)
    return {"fechamentos_by_venda": {f.venda_id: f for f in fechamentos}}


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
    },
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
    ],
    cadastrar_dep=require_operacao("vendas", "cadastrar"),
    editar_dep=require_operacao("vendas", "editar"),
    excluir_dep=require_operacao("vendas", "excluir"),
    pagina="vendas",
    campos_form_map={
        "cliente": "cliente_id",
        "veiculo": "veiculo_id",
        "data_venda": "data_venda",
        "valor_venda": "valor_venda",
        "valor_entrada": "valor_entrada",
        "debitos": "debitos",
        "km": "km",
        "veiculo_troca": "veiculo_troca_id",
        "valor_diferenca": "valor_diferenca",
        "pagamento_pendente": "pagamento_pendente",
        "valor_pendente": "valor_pendente",
        "datas_pagamento": "datas_pagamento",
        "forma_pagamento": "forma_pagamento",
        "parcelas": "parcelas",
        "status": "status",
        "observacoes": "observacoes",
    },
)


def _ok_venda(
    request: Request, session: Session, user: usuario.Usuario
) -> HTMLResponse:
    vendas = venda.list_all(session)
    return templates.TemplateResponse(
        request,
        "_vendas_ok.html",
        {"user": user, "vendas": vendas, **_ctx_lista_vendas(session, vendas)},
    )


def _erro_venda(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    msg: str,
    venda_obj: venda.Venda | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_form_venda.html",
        {
            **_ctx_form_venda(session),
            "venda": venda_obj,
            "user": user,
            "erro": msg,
        },
        status_code=400,
    )


def _persistir_contrato_venda(
    session: Session, obj: venda.Venda, actor_id: int | None = None
) -> None:
    upload_dir = _uploads_contrato_venda_dir(obj.id)
    filename = f"{uuid4().hex}.pdf"
    path = upload_dir / filename
    tmp_path = upload_dir / f".{filename}.tmp"
    pdf = documento_contrato_venda.gerar_pdf(obj)
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
    request: Request, session: SessionDep, user: _CadastrarVendaDep
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    form = await request.form()

    cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
    if erro:
        return _erro_venda(request, session, user, erro)

    if novo_cliente_data is not None:
        try:
            cliente_obj = cliente.create(session, novo_cliente_data, user.id)
        except IntegrityError:
            return rollback_integrity_error_response(
                session,
                lambda: _erro_venda(request, session, user, "Cliente já existe"),
            )
    assert cliente_obj is not None  # noqa: S101 -- invariante interna: erro is None garante cliente_obj definido

    try:
        data = venda.VendaCreate.model_validate(
            _filtrar_campos_ocultos_venda(
                user, {**_parse_venda_form(form), "cliente_id": cliente_obj.id}
            )
        )
        validate_cliente_veiculo_fks(session, data)
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)
    except (ValidationError, HTTPException) as exc:
        if novo_cliente_data is not None:
            session.rollback()
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_venda(request, session, user, msg)

    try:
        obj = venda.create(session, data, user.id)
        _persistir_contrato_venda(session, obj, user.id)
        whatsapp.notificar_venda(session, obj)
    except IntegrityError:
        return rollback_integrity_error_response(
            session, lambda: _erro_venda(request, session, user, "Venda já existe")
        )
    return _ok_venda(request, session, user)


@app.post("/ui/vendas/{item_id}")
async def _atualizar_venda(
    item_id: int, request: Request, session: SessionDep, user: _EditarVendaDep
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
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
        venda.update(session, obj, data)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: _erro_venda(
                request, session, user, "Venda já existe", venda_obj=obj
            ),
        )
    return _ok_venda(request, session, user)


@app.get("/ui/vendas/{item_id}/contrato")
def _baixar_contrato_venda(
    item_id: int, session: SessionDep, _: _BaixarContratoVendaDep
) -> RedirectResponse:
    obj = _found(venda.get(session, item_id), "Venda")
    documentos = documento_contrato_venda.list_by_venda(session, obj.id)
    if not documentos:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return RedirectResponse(documentos[-1].url)


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
    item_id: int, request: Request, session: SessionDep, user: _FecharVendaDep
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
        session.info["usuario_id"] = user.id
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
    vendas = venda.list_all(session)
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
