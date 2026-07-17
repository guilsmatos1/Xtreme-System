"""HTMX routes for vendas."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import (
    SessionDep,
    UIUser,
    _found,
    require_operacao,
    templates,
)
from xtreme_system.api.route_factories import _sort_key, register_crud_ui_routes
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploads_contrato_venda_dir,
)
from xtreme_system.api.routes.workflows import (
    recompute_vehicle_status_on_delete,
    validate_cliente_veiculo_fks,
    validate_veiculo_disponivel_para_venda,
)
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp

logger = structlog.get_logger(__name__)

# ---- Vendas (UI) ----

_CadastrarVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "cadastrar"))
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
    before_create=validate_cliente_veiculo_fks,
    before_update=validate_cliente_veiculo_fks,
    before_delete=recompute_vehicle_status_on_delete,
    after_create=whatsapp.notificar_venda,
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
    register_create=False,
    cadastrar_dep=require_operacao("vendas", "cadastrar"),
    editar_dep=require_operacao("vendas", "editar"),
    excluir_dep=require_operacao("vendas", "excluir"),
    pagina="vendas",
    campos_form_map={
        "valor_venda": "valor_venda",
        "valor_entrada": "valor_entrada",
        "debitos": "debitos",
        "valor_diferenca": "valor_diferenca",
        "valor_pendente": "valor_pendente",
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


def _erro_venda(request: Request, session: Session, msg: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_form_venda.html",
        {**_ctx_form_venda(session), "venda": None, "erro": msg},
        status_code=400,
    )


def _resolver_cliente(
    session: Session, form: Any
) -> tuple[cliente.Cliente | None, cliente.ClienteCreate | None, str | None]:
    """Retorna (cliente_existente, dados_novo_cliente, erro)."""
    cliente_sel = str(form.get("cliente_id") or "").strip()
    if cliente_sel:
        try:
            existente = cliente.get(session, int(cliente_sel))
        except ValueError:
            existente = None
        if existente is None:
            return None, None, "Cliente inválido ou inexistente"
        return existente, None, None

    nome = str(form.get("cli_nome") or "").strip()
    documento = str(form.get("cli_documento") or "").strip()
    erro: str | None = None
    if not nome or not documento:
        erro = "Informe os dados do cliente"
    elif cliente.get_by_documento(session, documento):
        erro = "CPF já cadastrado — selecione o cliente na lista"
    if erro:
        return None, None, erro
    try:
        novo_cliente_data = cliente.ClienteCreate.model_validate(
            {
                "nome": nome,
                "documento": documento,
                "tipo": form.get("cli_tipo") or "pessoa_fisica",
                "telefone": str(form.get("cli_telefone") or "").strip() or None,
                "email": str(form.get("cli_email") or "").strip() or None,
                "endereco": str(form.get("cli_endereco") or "").strip() or None,
                "cidade": str(form.get("cli_cidade") or "").strip() or None,
                "estado": str(form.get("cli_estado") or "").strip() or None,
                "cep": str(form.get("cli_cep") or "").strip() or None,
            }
        )
    except ValidationError:
        return None, None, "Dados do cliente inválidos"
    return None, novo_cliente_data, None


def _persistir_contrato_venda(session: Session, obj: venda.Venda) -> None:
    upload_dir = _uploads_contrato_venda_dir(obj.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.pdf"
    path = upload_dir / filename
    path.write_bytes(documento_contrato_venda.gerar_pdf(obj))
    try:
        documento_contrato_venda.create(
            session,
            documento_contrato_venda.DocumentoContratoVendaCreate(
                venda_id=obj.id,
                url=f"/static/uploads/vendas/{obj.id}/contrato/{filename}",
            ),
        )
    except Exception:
        _remover_upload(path)
        raise


@app.post("/ui/vendas")
async def _criar_venda(
    request: Request, session: SessionDep, user: _CadastrarVendaDep
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    form = await request.form()

    cliente_obj, novo_cliente_data, erro = _resolver_cliente(session, form)
    if erro:
        return _erro_venda(request, session, erro)

    if novo_cliente_data is not None:
        try:
            cliente_obj = cliente.create(session, novo_cliente_data)
        except IntegrityError:
            session.rollback()
            return _erro_venda(request, session, "Cliente já existe")
    assert cliente_obj is not None  # noqa: S101 -- invariante interna: erro is None garante cliente_obj definido

    try:
        data = venda.VendaCreate.model_validate(
            {**_parse_venda_form(form), "cliente_id": cliente_obj.id}
        )
        validate_cliente_veiculo_fks(session, data)
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)
    except (ValidationError, HTTPException) as exc:
        if novo_cliente_data is not None:
            session.rollback()
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_venda(request, session, msg)

    try:
        obj = venda.create(session, data)
        _persistir_contrato_venda(session, obj)
        whatsapp.notificar_venda(session, obj)
    except IntegrityError:
        session.rollback()
        return _erro_venda(request, session, "Venda já existe")
    return _ok_venda(request, session, user)


@app.get("/ui/vendas/{item_id}/contrato")
def _baixar_contrato_venda(
    item_id: int, session: SessionDep, _: UIUser
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
    fechamento_id: int, request: Request, session: SessionDep, user: UIUser
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
