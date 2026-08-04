"""Preparation pipeline for venda UI writes."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.responses import validation_error_detail
from xtreme_system.api.routes.ui_routes.client_resolution import resolver_cliente
from xtreme_system.api.routes.ui_routes.nested_writes import (
    NestedWrites,
    criar_aninhado_ou_resposta_conflito,
)
from xtreme_system.api.routes.ui_routes.vehicle_resolution import (
    resolver_veiculo_inline,
)
from xtreme_system.cliente import core as cliente
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.workflow.core import validate_venda_create, validate_venda_update


@dataclass(frozen=True)
class VendaPreparada:
    data: venda.VendaCreate | venda.VendaUpdate
    nested_writes: NestedWrites


@dataclass(frozen=True)
class VendaErro:
    mensagem: str | None = None
    conflito: str | None = None
    dados: dict[str, Any] = field(default_factory=dict)


def parse_venda_form(form: Any) -> dict[str, Any]:
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


def resolver_veiculo_troca(
    session: Session, form: Any
) -> tuple[veiculo.Veiculo | None, veiculo.VeiculoCreate | None, str | None]:
    veiculo_sel = str(form.get("veiculo_troca_id") or "").strip()
    if veiculo_sel:
        try:
            existente = veiculo.get(session, int(veiculo_sel))
        except ValueError:
            existente = None
        if existente is None:
            return None, None, "Veículo da troca inválido ou inexistente"
        return existente, None, None

    return resolver_veiculo_inline(
        session,
        form,
        prefix="veic_troca_",
        tipo_entrada=veiculo.TipoEntrada.compra,
        preco=str(form.get("veic_troca_preco") or "").strip(),
        required=False,
        error_label="do veículo da troca",
    )


def _validation_message(exc: ValidationError | HTTPException) -> str:
    return (
        str(exc.detail)
        if isinstance(exc, HTTPException)
        else validation_error_detail(exc)
    )


def _preparar_cliente(
    session: Session,
    form: Any,
    user: usuario.Usuario,
    dados_form: dict[str, Any],
    nested_writes: NestedWrites,
) -> tuple[cliente.Cliente | None, VendaErro | None]:
    cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
    if erro:
        return None, VendaErro(mensagem=erro, dados=dados_form)
    if novo_cliente_data is None:
        if cliente_obj is None:
            return None, VendaErro(
                mensagem="Informe os dados do cliente", dados=dados_form
            )
        return cliente_obj, None
    cliente_obj, conflito = criar_aninhado_ou_resposta_conflito(
        session,
        novo_cliente_data,
        cliente.create,
        user.id,
        nested_writes=nested_writes,
    )
    if conflito:
        return None, VendaErro(conflito="Cliente", dados=dados_form)
    return cliente_obj, None


def _preparar_veiculo_troca(
    session: Session,
    form: Any,
    user: usuario.Usuario,
    dados_form: dict[str, Any],
    nested_writes: NestedWrites,
) -> tuple[veiculo.Veiculo | None, VendaErro | None]:
    veiculo_troca_obj, novo_veiculo_troca_data, erro = resolver_veiculo_troca(
        session, form
    )
    if erro:
        nested_writes.rollback(session)
        return None, VendaErro(mensagem=erro, dados=dados_form)
    novo_veiculo_troca_obj, conflito = criar_aninhado_ou_resposta_conflito(
        session,
        novo_veiculo_troca_data,
        veiculo.create,
        user.id,
        nested_writes=nested_writes,
    )
    if conflito:
        return None, VendaErro(conflito="Veículo da troca", dados=dados_form)
    return novo_veiculo_troca_obj or veiculo_troca_obj, None


def _validar_venda(
    session: Session,
    user: usuario.Usuario,
    dados_venda: dict[str, Any],
    obj: venda.Venda | None,
) -> venda.VendaCreate | venda.VendaUpdate:
    dados_permitidos = perfil.campos_form_visiveis(user, "vendas", dados_venda)
    data: venda.VendaCreate | venda.VendaUpdate
    if obj is None:
        data = venda.VendaCreate.model_validate(dados_permitidos)
        validate_venda_create(session, data)
    else:
        data = venda.VendaUpdate.model_validate(dados_permitidos)
        validate_venda_update(session, obj, data)
    return data


def preparar_venda(
    session: Session,
    form: Any,
    user: usuario.Usuario,
    *,
    obj: venda.Venda | None = None,
) -> VendaPreparada | VendaErro:
    dados_form = dict(form)
    nested_writes = NestedWrites()

    cliente_obj: cliente.Cliente | None = None
    if obj is None:
        cliente_obj, erro_result = _preparar_cliente(
            session, form, user, dados_form, nested_writes
        )
        if erro_result:
            return erro_result

    veiculo_troca_obj, erro_result = _preparar_veiculo_troca(
        session, form, user, dados_form, nested_writes
    )
    if erro_result:
        return erro_result

    dados_venda: dict[str, Any] = {**parse_venda_form(form)}
    if obj is None:
        assert cliente_obj is not None  # noqa: S101
        dados_venda.update(cliente_id=cliente_obj.id, vendedor_id=user.id)
    if veiculo_troca_obj is not None:
        dados_venda["veiculo_troca_id"] = veiculo_troca_obj.id

    data: venda.VendaCreate | venda.VendaUpdate
    try:
        data = _validar_venda(session, user, dados_venda, obj)
    except (ValidationError, HTTPException) as exc:
        nested_writes.rollback(session)
        return VendaErro(mensagem=_validation_message(exc), dados=dados_form)

    return VendaPreparada(data=data, nested_writes=nested_writes)
