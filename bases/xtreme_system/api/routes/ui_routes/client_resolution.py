"""Resolve an existing or newly submitted client from UI forms."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.responses import validation_error_detail
from xtreme_system.cliente import core as cliente


def resolver_cliente(
    session: Session,
    form: Any,
    *,
    cliente_field: str = "cliente_id",
    required_msg: str = "Informe os dados do cliente",
    invalid_selected_msg: str = "Cliente inválido ou inexistente",
    invalid_new_msg: str = "Dados do cliente inválidos",
) -> tuple[cliente.Cliente | None, cliente.ClienteCreate | None, str | None]:
    """Return ``(existing_client, new_client_data, error)`` for a submitted form."""
    cliente_sel = str(form.get(cliente_field) or "").strip()
    if cliente_sel:
        try:
            existente = cliente.get(session, int(cliente_sel))
        except ValueError:
            existente = None
        if existente is None:
            return None, None, invalid_selected_msg
        return existente, None, None
    nome = str(form.get("cli_nome") or "").strip()
    documento = str(form.get("cli_documento") or "").strip()
    if not nome or not documento:
        return None, None, required_msg
    if cliente.get_by_documento(session, documento):
        return None, None, "CPF já cadastrado — selecione o cliente na lista"
    try:
        novo_cliente_data = cliente.ClienteCreate.model_validate(
            {
                "nome": nome,
                "documento": documento,
                "tipo": form.get("cli_tipo") or "pessoa_fisica",
                "telefone": str(form.get("cli_telefone") or "").strip() or None,
                "telefone2": str(form.get("cli_telefone2") or "").strip() or None,
                "email": str(form.get("cli_email") or "").strip() or None,
                "endereco": str(form.get("cli_endereco") or "").strip() or None,
                "cidade": str(form.get("cli_cidade") or "").strip() or None,
                "estado": str(form.get("cli_estado") or "").strip() or None,
                "cep": str(form.get("cli_cep") or "").strip() or None,
                "profissao": str(form.get("cli_profissao") or "").strip() or None,
            }
        )
    except ValidationError as exc:
        return None, None, validation_error_detail(exc) or invalid_new_msg
    return None, novo_cliente_data, None
