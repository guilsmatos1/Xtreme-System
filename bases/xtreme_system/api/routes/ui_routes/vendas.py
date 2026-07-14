"""HTMX routes for vendas."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fpdf import FPDF
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, UIUser, _found, templates
from xtreme_system.api.route_factories import _sort_key, register_crud_ui_routes
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploads_contrato_venda_dir,
)
from xtreme_system.api.routes.workflows import validate_cliente_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
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
        v.data_venda.isoformat(),
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
)


def _ok_venda(request: Request, session: Session, user: UIAdmin) -> HTMLResponse:
    vendas = venda.list_all(session)
    return templates.TemplateResponse(
        request,
        "_vendas_ok.html",
        {"user": user, "vendas": vendas},
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


def _gerar_contrato_pdf(obj: venda.Venda) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "CONTRATO DE VENDA", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    def _secao(titulo: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)

    def _linha(texto: str) -> None:
        pdf.multi_cell(0, 7, texto, new_x="LMARGIN", new_y="NEXT")

    _linha(f"Venda: #{obj.id}")
    _linha(f"Data: {obj.data_venda.isoformat() if obj.data_venda else '-'}")

    _secao("Cliente")
    _linha(f"Nome: {obj.cliente.nome}")
    _linha(f"CPF/CNPJ: {obj.cliente.documento}")
    _linha(f"Telefone: {obj.cliente.telefone or '-'}")
    _linha(f"Endereço: {obj.cliente.endereco or '-'}")

    _secao("Veículo")
    _linha(f"Modelo: {obj.veiculo.modelo}")
    _linha(f"Placa: {obj.veiculo.placa}")
    _linha(f"KM: {obj.km if obj.km is not None else '-'}")

    _secao("Condições")
    _linha(f"Valor da venda: R$ {obj.valor_venda:.2f}")
    _linha(
        f"Valor de entrada: R$ {obj.valor_entrada:.2f}"
        if obj.valor_entrada is not None
        else "Valor de entrada: -"
    )
    _linha(
        f"Débitos do veículo: R$ {obj.debitos:.2f}"
        if obj.debitos is not None
        else "Débitos do veículo: -"
    )
    _linha(
        f"Veículo da troca: {obj.veiculo_troca.modelo} ({obj.veiculo_troca.placa})"
        if obj.veiculo_troca is not None
        else "Veículo da troca: -"
    )
    _linha(
        f"Valor da diferença: R$ {obj.valor_diferenca:.2f}"
        if obj.valor_diferenca is not None
        else "Valor da diferença: -"
    )
    _linha(
        "Pagamento pendente: "
        f"{'Sim' if obj.pagamento_pendente else 'Não'}"
        f"{f' - R$ {obj.valor_pendente:.2f}' if obj.valor_pendente is not None else ''}"
    )
    _linha(f"Datas de pagamento: {obj.datas_pagamento or '-'}")
    _linha(f"Forma de pagamento: {obj.forma_pagamento}")
    _linha(f"Parcelas: {obj.parcelas}")
    _linha(f"Observações: {obj.observacoes or '-'}")

    return bytes(pdf.output())


def _salvar_contrato_venda(session: Session, obj: venda.Venda) -> None:
    upload_dir = _uploads_contrato_venda_dir(obj.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.pdf"
    path = upload_dir / filename
    path.write_bytes(_gerar_contrato_pdf(obj))
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
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    form = await request.form()

    cliente_obj, novo_cliente_data, erro = _resolver_cliente(session, form)
    if erro:
        return _erro_venda(request, session, erro)

    if novo_cliente_data is not None:
        cliente_obj = cliente.create(session, novo_cliente_data)
    assert cliente_obj is not None  # noqa: S101 -- invariante interna: erro is None garante cliente_obj definido

    try:
        data = venda.VendaCreate.model_validate(
            {**_parse_venda_form(form), "cliente_id": cliente_obj.id}
        )
        validate_cliente_veiculo_fks(session, data)
    except (ValidationError, HTTPException) as exc:
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_venda(request, session, msg)

    obj = venda.create(session, data)
    whatsapp.notificar_venda(session, obj)
    _salvar_contrato_venda(session, obj)
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
